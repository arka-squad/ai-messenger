use crate::domain::{
    journal::*,
    models::Attachment,
    ports::{PortError, RepositoryPort},
};
use serde::Deserialize;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{
    fs,
    io::Write,
    path::{Path, PathBuf},
};
use surrealdb::{
    engine::local::{Db, SurrealKv},
    Surreal,
};
use tokio::sync::Mutex;

const SCHEMA_VERSION: u8 = 4;

pub struct LocalStore {
    database: Surreal<Db>,
    blobs: PathBuf,
    writes: Mutex<()>,
}

#[derive(Deserialize)]
struct Record {
    #[serde(default)]
    payload: Value,
    #[serde(default)]
    encoded: Option<String>,
    journey: String,
    #[serde(default)]
    position: Option<u64>,
}
impl Record {
    fn mutation(&self) -> Result<Mutation, PortError> {
        match &self.encoded {
            Some(value) => serde_json::from_str(value),
            None => serde_json::from_value(self.payload.clone()),
        }
        .map_err(|_| PortError("Une mutation locale est illisible.".into()))
    }
}

impl LocalStore {
    pub async fn open(path: impl AsRef<Path>) -> Result<Self, PortError> {
        let path = path.as_ref();
        let database = Surreal::new::<SurrealKv>(path)
            .await
            .map_err(database_error)?;
        database
            .use_ns("messenger")
            .use_db("local")
            .await
            .map_err(database_error)?;
        database.query("DEFINE TABLE IF NOT EXISTS app_schema SCHEMALESS;
            DEFINE TABLE IF NOT EXISTS mutation SCHEMALESS;
            DEFINE INDEX IF NOT EXISTS mutation_content ON mutation FIELDS kind, mutation_id, fingerprint UNIQUE;
            DEFINE TABLE IF NOT EXISTS setting SCHEMALESS;
            DEFINE INDEX IF NOT EXISTS setting_key ON setting FIELDS key UNIQUE;
            DEFINE TABLE IF NOT EXISTS counter SCHEMALESS;
            DEFINE INDEX IF NOT EXISTS mutation_position ON mutation FIELDS position;")
            .await.map_err(database_error)?.check().map_err(database_error)?;
        let blobs = path.with_extension("attachments");
        fs::create_dir_all(&blobs)
            .map_err(|_| PortError("Les pièces jointes locales ne sont pas accessibles.".into()))?;
        let store = Self {
            database,
            blobs,
            writes: Mutex::new(()),
        };
        let version = store.schema_version().await?;
        if version > SCHEMA_VERSION {
            return Err(PortError(
                "Cette base a été ouverte par une version plus récente de Messenger.".into(),
            ));
        }
        if version < SCHEMA_VERSION {
            if version < 3 {
                store.migrate_previous_schema().await?;
            }
            store.position_journal().await?;
            store
                .database
                .query("UPSERT app_schema:current SET version = $version;")
                .bind(("version", SCHEMA_VERSION))
                .await
                .map_err(database_error)?
                .check()
                .map_err(database_error)?;
        }
        Ok(store)
    }

    async fn migrate_previous_schema(&self) -> Result<(), PortError> {
        // Old tables stay intact; an interrupted copy resumes before the version is advanced.
        for (table, kind) in [
            ("mail", "message"),
            ("marking", "marking"),
            ("approval", "approval"),
            ("verdict", "verdict"),
            ("reorientation", "reorientation"),
            ("request_closure", "closure"),
        ] {
            let mut response = self
                .database
                .query(format!("SELECT payload, journey FROM {table};"))
                .await
                .map_err(database_error)?;
            let rows: Vec<Record> = response.take(0).map_err(database_error)?;
            for row in rows {
                let mutation: Mutation =
                    serde_json::from_value(serde_json::json!({"kind":kind,"payload":row.payload}))
                        .map_err(|_| {
                            PortError(
                        "Une donnée de la base précédente est illisible. La base a été conservée."
                            .into(),
                    )
                        })?;
                self.save(&mutation, &row.journey).await?;
            }
        }
        let mut response = self
            .database
            .query("SELECT payload FROM delivery_route;")
            .await
            .map_err(database_error)?;
        let routes: Vec<Value> = response.take(0).map_err(database_error)?;
        for route in routes {
            if let Some(id) = route["payload"]["request_id"].as_str() {
                self.set_setting(&format!("route:{id}"), route["payload"].clone())
                    .await?;
            }
        }
        Ok(())
    }

    /// Version 4: every row already published or integrated gets its place, oldest first, so a
    /// cursor can replay this base from its beginning.
    async fn position_journal(&self) -> Result<(), PortError> {
        let mut response = self
            .database
            .query("SELECT payload, encoded, journey FROM mutation WHERE position = NONE AND (journey = 'published' OR journey = 'integrated');")
            .await
            .map_err(database_error)?;
        let rows: Vec<Record> = response.take(0).map_err(database_error)?;
        let mut mutations = rows
            .iter()
            .map(Record::mutation)
            .collect::<Result<Vec<_>, _>>()?;
        mutations.sort_by(|a, b| {
            (a.emitted_at(), a.kind(), a.id()).cmp(&(b.emitted_at(), b.kind(), b.id()))
        });
        for mutation in mutations {
            let position = self.next_position().await?;
            self.database.query("UPDATE mutation SET position = $position WHERE kind = $kind AND mutation_id = $id AND position = NONE AND journey != 'conflict';")
                .bind(("position", position)).bind(("kind", mutation.kind().to_owned())).bind(("id", mutation.id().to_owned()))
                .await.map_err(database_error)?.check().map_err(database_error)?;
        }
        Ok(())
    }

    /// Positions follow the order in which this base sees mutations become visible: published by
    /// this installation or integrated from the box. Callers hold `writes`.
    async fn next_position(&self) -> Result<u64, PortError> {
        let mut response = self
            .database
            .query("UPSERT counter:position SET value = (value ?? 0) + 1 RETURN VALUE value;")
            .await
            .map_err(database_error)?;
        let values: Vec<u64> = response.take(0).map_err(database_error)?;
        values
            .first()
            .copied()
            .ok_or_else(|| PortError("La position locale n’a pas pu être attribuée.".into()))
    }
}

impl RepositoryPort for LocalStore {
    async fn schema_version(&self) -> Result<u8, PortError> {
        let mut response = self
            .database
            .query("SELECT VALUE version FROM app_schema:current;")
            .await
            .map_err(database_error)?;
        let version: Option<u8> = response.take(0).map_err(database_error)?;
        Ok(version.unwrap_or(0))
    }

    async fn save(&self, mutation: &Mutation, journey: &str) -> Result<bool, PortError> {
        let _guard = self.writes.lock().await;
        let mut response = self.database.query("SELECT payload, encoded, journey FROM mutation WHERE kind = $kind AND mutation_id = $id AND journey != 'conflict';")
            .bind(("kind", mutation.kind().to_owned())).bind(("id", mutation.id().to_owned()))
            .await.map_err(database_error)?;
        let rows: Vec<Record> = response.take(0).map_err(database_error)?;
        let payload = serde_json::to_value(mutation)
            .map_err(|_| PortError("Cette donnée ne peut pas être enregistrée.".into()))?;
        if let Some(existing) = rows.first() {
            if existing.mutation()? != *mutation {
                return Err(PortError("mutation_en_conflit".into()));
            }
            return Ok(false);
        }
        let fingerprint = format!(
            "{:x}",
            Sha256::digest(
                canonical_bytes(&payload).map_err(|_| PortError("mutation_invalide".into()))?
            )
        );
        // Keep JSON as text: Surreal's object conversion removes null fields from imported immutable records.
        let encoded =
            serde_json::to_string(mutation).map_err(|_| PortError("mutation_invalide".into()))?;
        let position = if visible(journey) { Some(self.next_position().await?) } else { None };
        self.database.query("UPSERT mutation SET kind = $kind, mutation_id = $id, encoded = $encoded, journey = $journey, fingerprint = $fingerprint, position = $position WHERE kind = $kind AND mutation_id = $id AND fingerprint = $fingerprint;")
            .bind(("kind", mutation.kind().to_owned())).bind(("id", mutation.id().to_owned()))
            .bind(("encoded", encoded)).bind(("journey", journey.to_owned()))
            .bind(("fingerprint",fingerprint)).bind(("position", position))
            .await.map_err(database_error)?.check().map_err(database_error)?;
        Ok(true)
    }

    async fn mutations(
        &self,
        kind: Option<&str>,
        journey: Option<&str>,
    ) -> Result<Vec<StoredMutation>, PortError> {
        // Concrete predicates let Surreal use the kind index instead of scanning every mutation.
        let sql = match (kind.is_some(), journey.is_some()) {
            (true, true) => "SELECT payload, encoded, journey FROM mutation WHERE kind = $kind AND journey = $journey;",
            (true, false) => "SELECT payload, encoded, journey FROM mutation WHERE kind = $kind;",
            (false, true) => "SELECT payload, encoded, journey FROM mutation WHERE journey = $journey;",
            (false, false) => "SELECT payload, encoded, journey FROM mutation;",
        };
        let mut response = self
            .database
            .query(sql)
            .bind(("kind", kind.map(str::to_owned)))
            .bind(("journey", journey.map(str::to_owned)))
            .await
            .map_err(database_error)?;
        let rows: Vec<Record> = response.take(0).map_err(database_error)?;
        rows.into_iter()
            .map(|row| {
                Ok(StoredMutation {
                    mutation: row.mutation()?,
                    journey: row.journey,
                })
            })
            .collect()
    }

    async fn set_journey(&self, kind: &str, id: &str, journey: &str) -> Result<(), PortError> {
        if !visible(journey) {
            self.database.query("UPDATE mutation SET journey = $journey WHERE kind = $kind AND mutation_id = $id AND journey != 'conflict';")
                .bind(("kind",kind.to_owned())).bind(("id",id.to_owned())).bind(("journey",journey.to_owned()))
                .await.map_err(database_error)?.check().map_err(database_error)?;
            return Ok(());
        }
        // Becoming visible gives a row its place once; a later publication keeps it.
        let _guard = self.writes.lock().await;
        let position = self.next_position().await?;
        self.database.query("UPDATE mutation SET journey = $journey, position = position ?? $position WHERE kind = $kind AND mutation_id = $id AND journey != 'conflict';")
            .bind(("kind",kind.to_owned())).bind(("id",id.to_owned())).bind(("journey",journey.to_owned())).bind(("position", position))
            .await.map_err(database_error)?.check().map_err(database_error)?;
        Ok(())
    }

    async fn after(
        &self,
        position: u64,
        limit: usize,
    ) -> Result<Vec<(u64, StoredMutation)>, PortError> {
        let mut response = self
            .database
            .query("SELECT payload, encoded, journey, position FROM mutation WHERE position > $after ORDER BY position LIMIT $limit;")
            .bind(("after", position))
            .bind(("limit", limit as u64))
            .await
            .map_err(database_error)?;
        let rows: Vec<Record> = response.take(0).map_err(database_error)?;
        rows.into_iter()
            .map(|row| {
                Ok((
                    row.position.unwrap_or_default(),
                    StoredMutation { mutation: row.mutation()?, journey: row.journey },
                ))
            })
            .collect()
    }

    async fn setting(&self, key: &str) -> Result<Option<Value>, PortError> {
        let mut response = self
            .database
            .query("SELECT payload, encoded FROM setting WHERE key = $key LIMIT 1;")
            .bind(("key", key.to_owned()))
            .await
            .map_err(database_error)?;
        let rows: Vec<Value> = response.take(0).map_err(database_error)?;
        rows.into_iter()
            .next()
            .map(|row| match row["encoded"].as_str() {
                Some(text) => serde_json::from_str(text)
                    .map_err(|_| PortError("Un réglage local est illisible.".into())),
                None => Ok(row["payload"].clone()),
            })
            .transpose()
    }

    async fn set_setting(&self, key: &str, value: Value) -> Result<(), PortError> {
        let _guard = self.writes.lock().await;
        self.database
            .query("UPSERT setting SET key = $key, encoded = $encoded WHERE key = $key;")
            .bind(("key", key.to_owned()))
            .bind((
                "encoded",
                serde_json::to_string(&value).map_err(|_| PortError("reglage_invalide".into()))?,
            ))
            .await
            .map_err(database_error)?
            .check()
            .map_err(database_error)?;
        Ok(())
    }

    async fn save_blob(&self, reference: &Attachment, bytes: Vec<u8>) -> Result<(), PortError> {
        verify_blob(reference, &bytes)?;
        let _guard = self.writes.lock().await;
        let final_path = self.blobs.join(&reference.fingerprint);
        if final_path.exists() {
            let existing = fs::read(&final_path)
                .map_err(|_| PortError("La pièce jointe locale n’est pas lisible.".into()))?;
            if verify_blob(reference, &existing).is_ok() {
                return Ok(());
            }
        }
        let temporary = self.blobs.join(format!(".{}.tmp", uuid::Uuid::new_v4()));
        fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temporary)
            .and_then(|mut file| {
                file.write_all(&bytes)?;
                file.sync_all()
            })
            .and_then(|_| fs::rename(&temporary, &final_path))
            .map_err(|_| {
                PortError("La pièce jointe n’a pas pu être conservée sur cet ordinateur.".into())
            })?;
        let saved = fs::read(&final_path)
            .map_err(|_| PortError("La pièce jointe locale n’est pas lisible.".into()))?;
        verify_blob(reference, &saved)
    }

    async fn blob(&self, fingerprint: &str) -> Result<Option<Vec<u8>>, PortError> {
        if fingerprint.len() != 64 || !fingerprint.bytes().all(|b| b.is_ascii_hexdigit()) {
            return Err(PortError(
                "L’empreinte de la pièce jointe est invalide.".into(),
            ));
        }
        match fs::read(self.blobs.join(fingerprint)) {
            Ok(bytes) => Ok(Some(bytes)),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => Ok(None),
            Err(_) => Err(PortError(
                "La pièce jointe locale n’est pas lisible.".into(),
            )),
        }
    }
}

/// Published by this installation or integrated from the box: what gets a place for a cursor.
fn visible(journey: &str) -> bool {
    matches!(journey, "published" | "integrated")
}

pub fn verify_blob(reference: &Attachment, bytes: &[u8]) -> Result<(), PortError> {
    if reference.size != bytes.len() as u64
        || reference.fingerprint != format!("{:x}", Sha256::digest(bytes))
    {
        Err(PortError(
            "La pièce jointe est incomplète ou son empreinte ne correspond pas.".into(),
        ))
    } else {
        Ok(())
    }
}

fn database_error(_: surrealdb::Error) -> PortError {
    PortError("La base locale n’a pas pu terminer cette opération. Réessaie ; les données existantes sont conservées.".into())
}

#[cfg(test)]
#[path = "storage_tests.rs"]
mod tests;
