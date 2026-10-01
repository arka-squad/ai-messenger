use crate::{
    domain::{journal::*, models::Attachment, ports::*},
    mailbox::{hash, refusal, MailboxError, MailboxService},
};
use serde::Serialize;
use serde_json::{json, Value};
use std::{collections::BTreeMap, fs, path::Path};
#[derive(Clone, Serialize)]
pub struct MigrationPreview {
    pub fingerprint: String,
    pub source: String,
    pub messages: usize,
    pub accounts: usize,
    pub attachments: usize,
    pub missing_attachments: Vec<String>,
    pub counts: BTreeMap<String, BTreeMap<String, usize>>,
    #[serde(skip)]
    pub mutations: Vec<Mutation>,
    #[serde(skip)]
    pub blobs: Vec<(Attachment, Vec<u8>)>,
    #[serde(skip)]
    pub attachment_links: Vec<(String, Attachment)>,
    #[serde(skip)]
    pub box_metadata: Value,
    #[serde(skip)]
    pub manifest_metadata: Value,
}
pub fn preview(path: &Path) -> Result<MigrationPreview, MailboxError> {
    let source = if path.is_dir() {
        path.join("boite.json")
    } else {
        path.to_owned()
    };
    let directory = source.parent().ok_or_else(|| {
        refusal(
            "migration_source",
            "Le dossier de la boîte précédente est invalide.",
        )
    })?;
    let raw = fs::read(&source)
        .map_err(|_| refusal("migration_source", "La boîte précédente n’est pas lisible."))?;
    let box_: Value = serde_json::from_slice(&raw).map_err(|_| {
        refusal(
            "migration_source",
            "La boîte précédente n’est pas un JSON valide.",
        )
    })?;
    let manifest_path = if directory.join("boite.manifest.json").is_file() {
        directory.join("boite.manifest.json")
    } else {
        directory
            .parent()
            .unwrap_or(directory)
            .join("manifest.json")
    };
    let manifest_raw = fs::read(&manifest_path).map_err(|_| {
        refusal(
            "migration_manifeste",
            "Le manifeste des comptes doit accompagner la boîte.",
        )
    })?;
    let manifest: Value = serde_json::from_slice(&manifest_raw).map_err(|_| {
        refusal(
            "migration_manifeste",
            "Le manifeste des comptes est illisible.",
        )
    })?;
    let messages = box_["messages"]
        .as_array()
        .ok_or_else(|| refusal("migration_messages", "La liste des messages manque."))?;
    let accounts = manifest["comptes"]
        .as_array()
        .ok_or_else(|| refusal("migration_comptes", "La liste des comptes manque."))?;
    let mut ids = std::collections::BTreeSet::new();
    let mut mutations = Vec::new();
    let mut blobs = BTreeMap::new();
    let mut missing = Vec::new();
    let mut links = Vec::new();
    let mut counts: BTreeMap<String, BTreeMap<String, usize>> = BTreeMap::new();
    let mut proof = raw;
    proof.extend(manifest_raw);
    for message in messages {
        let id = message["id"].as_str().ok_or_else(|| {
            refusal(
                "migration_identifiant",
                "Un message précédent n’a pas d’identifiant.",
            )
        })?;
        if !crate::domain::models::safe_id(id) {
            return Err(refusal(
                "migration_identifiant",
                "Un identifiant de l’ancienne boîte n’est pas utilisable sur tous les postes.",
            ));
        }
        if !ids.insert(id.to_owned()) {
            return Err(refusal(
                "migration_doublon",
                "La boîte précédente contient des identifiants de message répétés.",
            ));
        }
        mutations.push(Mutation::LegacyMessage(message.clone()));
        if let Some(recipients) = message["a"].as_array() {
            for recipient in recipients.iter().filter_map(Value::as_str) {
                let status = message["statuts"][recipient]
                    .as_str()
                    .or_else(|| message["statut"].as_str())
                    .unwrap_or("nouveau");
                *counts
                    .entry(recipient.into())
                    .or_default()
                    .entry(status.into())
                    .or_default() += 1;
            }
        }
        if let Some(name) = message["pj"].as_str().filter(|s| !s.is_empty()) {
            let relative = Path::new(name);
            if relative.is_absolute()
                || relative
                    .components()
                    .any(|c| !matches!(c, std::path::Component::Normal(_)))
            {
                return Err(refusal(
                    "migration_piece_jointe",
                    "Une pièce jointe sort du dossier de la boîte. Rien n’a été importé.",
                ));
            }
            let path = [
                directory.join(relative),
                directory
                    .parent()
                    .unwrap_or(directory)
                    .join("pj")
                    .join(relative),
            ]
            .into_iter()
            .find(|p| p.is_file());
            if let Some(path) = path {
                let canonical = path.canonicalize().map_err(|_| {
                    refusal(
                        "migration_piece_jointe",
                        "Une pièce jointe n’est pas accessible.",
                    )
                })?;
                let allowed = directory.canonicalize().map_err(|_| {
                    refusal(
                        "migration_source",
                        "Le dossier précédent n’est pas accessible.",
                    )
                })?;
                let modern = directory
                    .parent()
                    .unwrap_or(directory)
                    .join("pj")
                    .canonicalize()
                    .ok();
                if !canonical.starts_with(&allowed)
                    && !modern.as_ref().is_some_and(|p| canonical.starts_with(p))
                {
                    return Err(refusal(
                        "migration_piece_jointe",
                        "Une pièce jointe pointe hors de la boîte.",
                    ));
                }
                let bytes = fs::read(canonical).map_err(|_| {
                    refusal(
                        "migration_piece_jointe",
                        "Une pièce jointe n’est pas lisible.",
                    )
                })?;
                let reference = Attachment {
                    name: relative
                        .file_name()
                        .unwrap_or_default()
                        .to_string_lossy()
                        .into_owned(),
                    fingerprint: hash(&bytes),
                    size: bytes.len() as u64,
                };
                proof.extend(reference.fingerprint.as_bytes());
                links.push((id.into(), reference.clone()));
                blobs.insert(reference.fingerprint.clone(), (reference, bytes));
            } else {
                missing.push(name.into());
                proof.extend(format!("absent:{name}").as_bytes());
            }
        }
    }
    let mut addresses = std::collections::BTreeSet::new();
    for account in accounts {
        let address = account["nom"]
            .as_str()
            .ok_or_else(|| refusal("migration_compte", "Un compte précédent n’a pas d’adresse."))?;
        if !crate::domain::models::safe_id(address) {
            return Err(refusal(
                "migration_compte",
                "Une adresse de l’ancien manifeste n’est pas utilisable sur tous les postes.",
            ));
        }
        if !addresses.insert(address) {
            return Err(refusal(
                "migration_doublon",
                "Le manifeste contient des comptes répétés.",
            ));
        }
        mutations.push(Mutation::LegacyAccount(account.clone()));
    }
    let mut box_metadata = box_.clone();
    box_metadata.as_object_mut().unwrap().remove("messages");
    let mut manifest_metadata = manifest.clone();
    manifest_metadata.as_object_mut().unwrap().remove("comptes");
    Ok(MigrationPreview {
        fingerprint: hash(&proof),
        source: source.to_string_lossy().into_owned(),
        messages: messages.len(),
        accounts: accounts.len(),
        attachments: blobs.len(),
        missing_attachments: missing,
        counts,
        mutations,
        blobs: blobs.into_values().collect(),
        attachment_links: links,
        box_metadata,
        manifest_metadata,
    })
}
pub async fn apply<R: RepositoryPort, E: ExchangePort>(
    mailbox: &MailboxService<R, E>,
    source: &Path,
    fingerprint: &str,
) -> Result<MigrationPreview, MailboxError> {
    let _guard = mailbox.changes.lock().await;
    let plan = preview(source)?;
    if plan.fingerprint != fingerprint {
        return Err(refusal(
            "migration_source_modifiee",
            "La boîte précédente a changé. Relis le nouvel aperçu avant d’importer.",
        ));
    }
    if mailbox.setting("migration_complete").await?.is_some() {
        return Err(refusal(
            "migration_deja_faite",
            "Cette installation a déjà repris une boîte précédente.",
        ));
    }
    if mailbox
        .setting("migration_in_progress")
        .await?
        .is_some_and(|v| v.as_str() != Some(fingerprint))
    {
        return Err(refusal(
            "migration_reprise",
            "Un import interrompu doit reprendre exactement la source déjà vérifiée.",
        ));
    }
    mailbox
        .set_setting("migration_in_progress", json!(fingerprint))
        .await?;
    // An interrupted import repeats identical immutable records; it never wakes an agent.
    for (reference, bytes) in &plan.blobs {
        mailbox.store.save_blob(reference, bytes.clone()).await?;
        mailbox
            .exchange
            .deposit(ExchangeItem::Attachment { reference, bytes })?;
    }
    for mutation in &plan.mutations {
        mailbox.store.save(mutation, "migration_pending").await?;
        mailbox.exchange.deposit(ExchangeItem::Mutation(mutation))?;
        mailbox
            .store
            .set_journey(mutation.kind(), mutation.id(), "integrated")
            .await?;
    }
    for (id, reference) in &plan.attachment_links {
        let event = Event {
            id: format!("migration-attachment-{}", hash(id.as_bytes())),
            emitted_at: crate::mailbox::now(),
            installation: mailbox.installation.clone(),
            change: Change::LegacyAttachment {
                message_id: id.clone(),
                reference: reference.clone(),
            },
        };
        let key = format!("migration_link:{id}");
        let event = match mailbox.setting(&key).await? {
            Some(v) => serde_json::from_value(v)
                .map_err(|_| refusal("migration_reprise", "Le point de reprise est illisible."))?,
            None => {
                mailbox.set_setting(&key, json!(event)).await?;
                event
            }
        };
        confirmed(mailbox.publish(Mutation::Event(event)).await?)?;
    }
    let imported = match mailbox.setting("migration_imported_event").await? {
        Some(value) => serde_json::from_value(value)
            .map_err(|_| refusal("migration_reprise", "Le point de reprise est illisible."))?,
        None => {
            let event = Event {
                id: format!("migration-{}", plan.fingerprint),
                emitted_at: crate::mailbox::now(),
                installation: mailbox.installation.clone(),
                change: Change::Imported {
                    source_fingerprint: plan.fingerprint.clone(),
                    box_metadata: plan.box_metadata.clone(),
                    manifest_metadata: plan.manifest_metadata.clone(),
                },
            };
            mailbox
                .set_setting("migration_imported_event", json!(event))
                .await?;
            event
        }
    };
    confirmed(mailbox.publish(Mutation::Event(imported)).await?)?;
    mailbox
        .set_setting(
            "migration_complete",
            json!({"fingerprint":plan.fingerprint,"counts":plan.counts,"source":plan.source}),
        )
        .await?;
    mailbox
        .set_setting("notification_baseline", json!(true))
        .await?;
    Ok(plan)
}
fn confirmed(proof: String) -> Result<(), MailboxError> {
    if proof == "pending" {
        Err(refusal(
            "migration_en_attente",
            "La boîte n’a pas confirmé tout l’import. Il reste reprenable avec cette même source.",
        ))
    } else {
        Ok(())
    }
}
#[cfg(test)]
#[path = "migration_tests.rs"]
mod tests;
