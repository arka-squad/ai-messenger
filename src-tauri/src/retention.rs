use crate::{
    domain::{journal::*, ports::PortError},
    exchange::{fingerprint, read_mutation, DirectoryExchange},
    mailbox::{hash, new_id, now},
};
use chrono::{DateTime, Months, NaiveDate, Utc};
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs,
    path::PathBuf,
};
#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct RetentionPreview {
    pub fingerprint: String,
    pub mutations: usize,
    pub attachments: usize,
    pub bytes: u64,
    pub protected: usize,
    pub dormant: Vec<String>,
    pub installation_count: usize,
    pub oldest_allowed: String,
    #[serde(skip)]
    paths: Vec<(PathBuf, String)>,
    #[serde(skip)]
    removed: Vec<String>,
}
pub fn preview(exchange: &DirectoryExchange) -> Result<RetentionPreview, PortError> {
    let _gate = exchange.gate(false)?;
    plan(exchange, Utc::now().date_naive())
}
fn date(value: &str) -> Option<NaiveDate> {
    DateTime::parse_from_rfc3339(value)
        .ok()
        .map(|d| d.date_naive())
        .or_else(|| {
            value
                .get(..10)
                .and_then(|v| NaiveDate::parse_from_str(v, "%Y-%m-%d").ok())
        })
}
fn plan(exchange: &DirectoryExchange, today: NaiveDate) -> Result<RetentionPreview, PortError> {
    let year = today
        .checked_sub_months(Months::new(12))
        .ok_or_else(|| PortError("date_invalide".into()))?;
    let six = today
        .checked_sub_months(Months::new(6))
        .ok_or_else(|| PortError("date_invalide".into()))?;
    let checkpoints = exchange.checkpoints()?;
    let active = checkpoints
        .iter()
        .filter(|c| date(&c.seen_at).is_none_or(|d| d >= six))
        .collect::<Vec<_>>();
    let dormant = checkpoints
        .iter()
        .filter(|c| date(&c.seen_at).is_some_and(|d| d < six))
        .map(|c| c.id.clone())
        .collect::<Vec<_>>();
    let mut records = BTreeMap::new();
    let mut proof = BTreeMap::new();
    for path in exchange.all_paths()? {
        let mutation = read_mutation(&path)?;
        let key = format!("{}:{}", mutation.kind(), mutation.id());
        let bytes = fs::read(&path).map_err(|_| PortError("lecture_incomplete".into()))?;
        let content =
            hash(&canonical_bytes(&mutation).map_err(|_| PortError("lecture_incomplete".into()))?);
        let publication_day = path
            .parent()
            .and_then(|p| p.strip_prefix(exchange.root()).ok())
            .and_then(|p| date(&p.to_string_lossy().replace(['/', '\\'], "-")));
        let old = date(mutation.emitted_at()).is_some_and(|d| d < year)
            && publication_day.is_some_and(|d| d < year);
        let seen = !active.is_empty()
            && active
                .iter()
                .all(|c| c.integrated.get(&key) == Some(&content));
        let configuration = matches!(
            &mutation,
            Mutation::LegacyAccount(_)
                | Mutation::Event(Event {
                    change: Change::Account { .. }
                        | Change::Merge { .. }
                        | Change::File { .. }
                        | Change::Contacts { .. }
                        | Change::Imported { .. }
                        | Change::Purged { .. },
                    ..
                })
        );
        proof.insert(path.to_string_lossy().into_owned(), hash(&bytes));
        records.insert(
            key,
            (
                path,
                mutation,
                old && seen && !configuration,
                hash(&bytes),
                bytes.len() as u64,
            ),
        );
    }
    let closed = records
        .values()
        .filter_map(|r| match &r.1 {
            Mutation::Closure(v) => Some(v.request_id.clone()),
            _ => None,
        })
        .collect::<BTreeSet<_>>();
    for row in records.values_mut() {
        if let Mutation::Approval(request) = &row.1 {
            if !closed.contains(&request.id) {
                row.2 = false;
            }
        }
    }
    // Keep the ancestors and state records of anything still retained.
    loop {
        let retained = records
            .values()
            .filter(|r| !r.2)
            .flat_map(|r| dependencies(&r.1))
            .collect::<BTreeSet<_>>();
        let mut changed = false;
        for key in retained {
            if let Some(row) = records.get_mut(&key) {
                if row.2 {
                    row.2 = false;
                    changed = true;
                }
            }
        }
        // A marking or request result must not outlive its parent, nor vanish before a retained parent.
        let protected_messages = records
            .iter()
            .filter(|(_, r)| {
                !r.2 && matches!(r.1, Mutation::Message(_) | Mutation::LegacyMessage(_))
            })
            .map(|(_, r)| r.1.id().to_owned())
            .collect::<BTreeSet<_>>();
        let protected_requests = records
            .iter()
            .filter(|(_, r)| !r.2 && matches!(r.1, Mutation::Approval(_)))
            .map(|(_, r)| r.1.id().to_owned())
            .collect::<BTreeSet<_>>();
        for row in records.values_mut() {
            let retain = match &row.1 {
                Mutation::Marking(v) => protected_messages.contains(&v.message_id),
                Mutation::Verdict(v) => protected_requests.contains(&v.request_id),
                Mutation::Reorientation(v) => protected_requests.contains(&v.request_id),
                Mutation::Closure(v) => protected_requests.contains(&v.request_id),
                Mutation::Event(Event {
                    change: Change::Taken { request_id },
                    ..
                }) => protected_requests.contains(request_id),
                Mutation::Event(Event {
                    change:
                        Change::Integrated { message_id, .. }
                        | Change::Reached { message_id, .. }
                        | Change::AttachmentRequested { message_id, .. }
                        | Change::LegacyAttachment { message_id, .. },
                    ..
                }) => protected_messages.contains(message_id),
                _ => false,
            };
            if retain && row.2 {
                row.2 = false;
                changed = true;
            }
        }
        if !changed {
            break;
        }
    }
    let referenced = records
        .values()
        .filter(|r| !r.2)
        .filter_map(|r| attachment_hash(&r.1))
        .collect::<BTreeSet<_>>();
    let mut paths = Vec::new();
    let mut removed = Vec::new();
    let mut bytes = 0;
    let protected = records.values().filter(|r| !r.2).count();
    for (key, (path, _, eligible, hash, size)) in &records {
        if *eligible {
            paths.push((path.clone(), hash.clone()));
            removed.push(key.clone());
            bytes += size;
        }
    }
    let mutations = paths.len();
    let directory = exchange.root().join("attachments");
    if directory.is_dir() {
        for entry in fs::read_dir(directory).map_err(|_| PortError("lecture_incomplete".into()))? {
            let entry = entry.map_err(|_| PortError("lecture_incomplete".into()))?;
            let path = entry.path();
            let name = entry.file_name().to_string_lossy().into_owned();
            if !entry
                .file_type()
                .map_err(|_| PortError("lecture_incomplete".into()))?
                .is_file()
            {
                continue;
            }
            let old = entry
                .metadata()
                .and_then(|m| m.modified())
                .ok()
                .map(DateTime::<Utc>::from)
                .is_some_and(|d| d.date_naive() < year);
            if old && name.len() == 64 && !referenced.contains(&name) {
                let data = fs::read(&path).map_err(|_| PortError("lecture_incomplete".into()))?;
                proof.insert(path.to_string_lossy().into_owned(), hash(&data));
                bytes += data.len() as u64;
                paths.push((path, hash(&data)));
            }
        }
    }
    for checkpoint in &checkpoints {
        proof.insert(
            format!("installation:{}", checkpoint.id),
            hash(
                &serde_json::to_vec(&(
                    &checkpoint.integrated,
                    date(&checkpoint.seen_at).is_some_and(|d| d < six),
                ))
                .map_err(|_| PortError("lecture_incomplete".into()))?,
            ),
        );
    }
    let fingerprint = hash(
        &serde_json::to_vec(&(
            &proof,
            &removed,
            &paths
                .iter()
                .map(|p| p.0.to_string_lossy())
                .collect::<Vec<_>>(),
        ))
        .map_err(|_| PortError("lecture_incomplete".into()))?,
    );
    Ok(RetentionPreview {
        fingerprint,
        mutations,
        attachments: paths.len() - mutations,
        bytes,
        protected,
        dormant,
        installation_count: checkpoints.len(),
        oldest_allowed: year.to_string(),
        paths,
        removed,
    })
}
fn dependencies(mutation: &Mutation) -> Vec<String> {
    match mutation {
        Mutation::Message(v) => v
            .reply_to
            .iter()
            .flat_map(|id| [format!("message:{id}"), format!("legacy_message:{id}")])
            .collect(),
        Mutation::LegacyMessage(v) => v["re"]
            .as_str()
            .map(|id| vec![format!("legacy_message:{id}")])
            .unwrap_or_default(),
        Mutation::Marking(v) => vec![
            format!("message:{}", v.message_id),
            format!("legacy_message:{}", v.message_id),
        ],
        Mutation::Verdict(v) => vec![format!("approval:{}", v.request_id)],
        Mutation::Reorientation(v) => vec![format!("approval:{}", v.request_id)],
        Mutation::Closure(v) => vec![format!("approval:{}", v.request_id)],
        Mutation::Event(Event {
            change:
                Change::LegacyAttachment { message_id, .. }
                | Change::Integrated { message_id, .. }
                | Change::Reached { message_id, .. }
                | Change::AttachmentRequested { message_id, .. },
            ..
        }) => vec![
            format!("message:{message_id}"),
            format!("legacy_message:{message_id}"),
        ],
        Mutation::Event(Event {
            change: Change::Taken { request_id },
            ..
        }) => vec![format!("approval:{request_id}")],
        _ => Vec::new(),
    }
}
fn attachment_hash(mutation: &Mutation) -> Option<String> {
    match mutation {
        Mutation::Message(v) => v.attachment.as_ref().map(|a| a.fingerprint.clone()),
        Mutation::Event(Event {
            change: Change::LegacyAttachment { reference, .. },
            ..
        }) => Some(reference.fingerprint.clone()),
        _ => None,
    }
}
pub fn apply(
    exchange: &DirectoryExchange,
    expected: &str,
    installation: &str,
) -> Result<RetentionPreview, PortError> {
    let _gate = exchange.gate(true)?;
    let plan = plan(exchange, Utc::now().date_naive())?;
    if plan.fingerprint != expected {
        return Err(PortError("apercu_conservation_modifie".into()));
    }
    if plan.paths.is_empty() {
        return Ok(plan);
    }
    let notice = Mutation::Event(Event {
        id: new_id(),
        emitted_at: now(),
        installation: installation.into(),
        change: Change::Purged {
            removed: plan.removed.clone(),
            dormant: plan.dormant.clone(),
        },
    });
    exchange.publish_under_gate(&notice)?;
    for (path, expected) in &plan.paths {
        if fingerprint(&fs::read(path).map_err(|_| PortError("suppression_interrompue".into()))?)
            != *expected
        {
            return Err(PortError("suppression_interrompue".into()));
        }
        fs::remove_file(path).map_err(|_| PortError("suppression_interrompue".into()))?;
    }
    Ok(plan)
}
#[cfg(test)]
#[path = "retention_tests.rs"]
mod tests;
