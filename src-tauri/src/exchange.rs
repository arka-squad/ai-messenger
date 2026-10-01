use crate::domain::{
    journal::*,
    models::Attachment,
    ports::{ExchangePort, PortError},
};
use chrono::{Datelike, Duration as Days, NaiveDate, Utc};
use notify::{RecursiveMode, Watcher};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{
    collections::BTreeMap,
    fs,
    io::Write,
    path::{Path, PathBuf},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Mutex,
    },
    thread,
    time::Duration,
};

#[derive(Clone)]
pub struct DirectoryExchange {
    root: Arc<PathBuf>,
    cursor_directory: Option<PathBuf>,
    atomic: Arc<AtomicBool>,
    watcher: Arc<Mutex<Option<notify::RecommendedWatcher>>>,
    watcher_failed: Arc<AtomicBool>,
    changes: tokio::sync::watch::Sender<u64>,
    publications: Arc<Mutex<BTreeMap<String, String>>>,
}

#[derive(Deserialize, Serialize)]
struct Envelope {
    mutation: Mutation,
    fingerprint: String,
}

impl DirectoryExchange {
    pub fn new(root: impl Into<PathBuf>) -> Self {
        let (changes, _) = tokio::sync::watch::channel(0);
        Self {
            root: Arc::new(root.into()),
            cursor_directory: None,
            atomic: Arc::new(AtomicBool::new(true)),
            watcher: Arc::new(Mutex::new(None)),
            watcher_failed: Arc::new(AtomicBool::new(false)),
            changes,
            publications: Arc::new(Mutex::new(BTreeMap::new())),
        }
    }

    pub fn with_cursor(root: impl Into<PathBuf>, cursor_directory: impl Into<PathBuf>) -> Self {
        Self {
            cursor_directory: Some(cursor_directory.into()),
            ..Self::new(root)
        }
    }

    pub fn root(&self) -> PathBuf {
        (*self.root).clone()
    }
    pub fn reachable(&self) -> bool {
        fs::read_dir(self.root()).is_ok()
    }
    pub fn atomic_publication(&self) -> bool {
        self.atomic.load(Ordering::Relaxed)
    }
    pub fn listening(&self) -> bool {
        !self.watcher_failed.load(Ordering::Relaxed)
            && self.watcher.lock().expect("watcher lock").is_some()
    }
    pub fn gate(&self, exclusive: bool) -> Result<fs::File, PortError> {
        if !self.reachable() {
            return Err(PortError("emplacement_injoignable".into()));
        }
        let file = fs::OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(self.root().join(".messenger.lock"))
            .map_err(location_error)?;
        let locked = if exclusive {
            file.try_lock()
        } else {
            file.try_lock_shared()
        };
        locked.map_err(|_| PortError("boite_occupee".into()))?;
        Ok(file)
    }
    pub(crate) fn publish_under_gate(&self, mutation: &Mutation) -> Result<String, PortError> {
        self.publish_mutation(mutation)
    }

    fn publication_path(&self, mutation: &Mutation) -> Result<PathBuf, PortError> {
        validate_id(mutation.id())?;
        let kind = if matches!(mutation, Mutation::Verdict(_) | Mutation::Reorientation(_)) {
            "decision"
        } else {
            mutation.kind()
        };
        let key = format!("{}-{}", kind, mutation.id());
        let root = self.root();
        let namespace = fingerprint(root.to_string_lossy().as_bytes());
        let index = self
            .cursor_directory
            .as_ref()
            .map(|directory| directory.join(&namespace).join(&key));
        if let Some(path) = &index {
            if let Ok(day) = fs::read_to_string(path) {
                if valid_day(&day) {
                    let candidate = root.join(day.replace('-', "/")).join(format!("{key}.json"));
                    if candidate.exists() {
                        return Ok(candidate);
                    }
                }
            }
        }
        if let Some(day) = self
            .publications
            .lock()
            .expect("publication lock")
            .get(&key)
        {
            let candidate = root.join(day.replace('-', "/")).join(format!("{key}.json"));
            if candidate.exists() {
                return Ok(candidate);
            }
        }
        // Recover a deposit made before a crash, before a local proof could be recorded.
        for offset in 0..=7 {
            let day = (Utc::now().date_naive() - Days::days(offset)).to_string();
            let candidate = root.join(day.replace('-', "/")).join(format!("{key}.json"));
            if candidate.is_file() {
                return Ok(candidate);
            }
        }
        // ponytail: at ~30 deposits/day, scan older day names once per uncached ID; add a shared index only if SMB measurements warrant it.
        for directory in scan_days(&root, None)? {
            let candidate = directory.join(format!("{key}.json"));
            if candidate.is_file() {
                return Ok(candidate);
            }
        }
        let day = Utc::now().date_naive().to_string();
        if let Some(path) = &index {
            fs::create_dir_all(path.parent().expect("publication index parent"))
                .map_err(location_error)?;
            atomic_replace(path, day.as_bytes())?;
        }
        self.publications
            .lock()
            .expect("publication lock")
            .insert(key.clone(), day.clone());
        Ok(root.join(day.replace('-', "/")).join(format!("{key}.json")))
    }

    fn publish_mutation(&self, mutation: &Mutation) -> Result<String, PortError> {
        if !self.reachable() {
            return Err(PortError("emplacement_injoignable".into()));
        }
        let path = self.publication_path(mutation)?;
        let hash = fingerprint(&canonical_bytes(mutation).map_err(invalid_record)?);
        let bytes = serde_json::to_vec(&Envelope {
            mutation: mutation.clone(),
            fingerprint: hash.clone(),
        })
        .map_err(invalid_record)?;
        self.publish_bytes(&path, &bytes)?;
        let proof = read_mutation(&path)?;
        if proof != *mutation {
            return Err(PortError("lecture_incomplete".into()));
        }
        Ok(hash)
    }

    fn publish_bytes(&self, path: &Path, bytes: &[u8]) -> Result<(), PortError> {
        fs::create_dir_all(
            path.parent()
                .ok_or_else(|| PortError("depot_refuse".into()))?,
        )
        .map_err(location_error)?;
        if path.exists() {
            return same_or_conflict(path, bytes);
        }
        let temporary = path
            .parent()
            .unwrap()
            .join(format!(".{}.tmp", uuid::Uuid::new_v4()));
        let mut file = fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&temporary)
            .map_err(location_error)?;
        file.write_all(bytes)
            .and_then(|_| file.sync_all())
            .map_err(location_error)?;
        // Publishing a hard link and removing the temporary name provides atomic visibility
        // without the replacement race of std::fs::rename on macOS.
        let outcome = match fs::hard_link(&temporary, path) {
            Ok(()) => Ok(()),
            Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => {
                same_or_conflict(path, bytes)
            }
            Err(_) => {
                self.atomic.store(false, Ordering::Relaxed);
                match fs::OpenOptions::new()
                    .write(true)
                    .create_new(true)
                    .open(path)
                {
                    Ok(mut target) => {
                        let written = target.write_all(bytes).and_then(|_| target.sync_all());
                        if written.is_err() {
                            let _ = fs::remove_file(path);
                        }
                        written.map_err(location_error)
                    }
                    Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => {
                        same_or_conflict(path, bytes)
                    }
                    Err(error) => Err(location_error(error)),
                }
            }
        };
        let _ = fs::remove_file(&temporary);
        outcome?;
        if fs::read(path).map_err(location_error)? != bytes {
            return Err(PortError("lecture_incomplete".into()));
        }
        Ok(())
    }

    pub fn all_paths(&self) -> Result<Vec<PathBuf>, PortError> {
        let mut paths = Vec::new();
        for day in scan_days(&self.root(), None)? {
            for entry in fs::read_dir(day).map_err(location_error)? {
                let path = entry.map_err(location_error)?.path();
                if path.extension().is_some_and(|v| v == "json") {
                    paths.push(path);
                }
            }
        }
        paths.sort();
        Ok(paths)
    }

    pub fn checkpoints(&self) -> Result<Vec<ReadCheckpoint>, PortError> {
        let directory = self.root().join("installations");
        if !directory.exists() {
            return Ok(Vec::new());
        }
        let mut result = Vec::new();
        for entry in fs::read_dir(directory).map_err(location_error)? {
            let path = entry.map_err(location_error)?.path();
            if path.extension().is_some_and(|v| v == "json") {
                let bytes = fs::read(path).map_err(location_error)?;
                result.push(serde_json::from_slice(&bytes).map_err(invalid_record)?);
            }
        }
        Ok(result)
    }
}

impl ExchangePort for DirectoryExchange {
    fn deposit(&self, item: ExchangeItem<'_>) -> Result<String, PortError> {
        // One mailbox-wide native lock serializes publication and human retention, including a publication crossing midnight.
        let _gate = retry(|| self.gate(true))?;
        match item {
            ExchangeItem::Mutation(mutation) => retry(|| self.publish_mutation(mutation)),
            ExchangeItem::Attachment { reference, bytes } => {
                if !self.reachable() {
                    return Err(PortError("emplacement_injoignable".into()));
                }
                verify_attachment(reference, bytes)?;
                let path = self.root().join("attachments").join(&reference.fingerprint);
                if let Ok(existing) = fs::read(&path) {
                    if verify_attachment(reference, &existing).is_err() {
                        let quarantine = path.with_file_name(format!(
                            ".corrupt-{}-{}.tmp",
                            reference.fingerprint,
                            uuid::Uuid::new_v4()
                        ));
                        fs::rename(&path, quarantine).map_err(location_error)?;
                    }
                }
                retry(|| self.publish_bytes(&path, bytes))?;
                Ok(reference.fingerprint.clone())
            }
            ExchangeItem::Checkpoint(checkpoint) => {
                if !self.reachable() {
                    return Err(PortError("emplacement_injoignable".into()));
                }
                validate_id(&checkpoint.id)?;
                let path = self
                    .root()
                    .join("installations")
                    .join(format!("{}.json", checkpoint.id));
                let bytes = serde_json::to_vec(checkpoint).map_err(invalid_record)?;
                atomic_replace(&path, &bytes)?;
                let restored: ReadCheckpoint =
                    serde_json::from_slice(&fs::read(path).map_err(location_error)?)
                        .map_err(invalid_record)?;
                if restored != *checkpoint {
                    return Err(PortError("lecture_incomplete".into()));
                }
                Ok(fingerprint(&bytes))
            }
        }
    }

    fn list(
        &self,
        since: Option<&str>,
        attachments: &[Attachment],
    ) -> Result<ExchangeBatch, PortError> {
        let _gate = retry(|| self.gate(false))?;
        if !self.reachable() {
            return Err(PortError("emplacement_injoignable".into()));
        }
        let mut batch = ExchangeBatch::default();
        for directory in scan_days(&self.root(), since)? {
            let mut entries: Vec<_> = fs::read_dir(directory)
                .map_err(location_error)?
                .filter_map(Result::ok)
                .map(|entry| entry.path())
                .collect();
            entries.sort();
            for path in entries {
                if !path.extension().is_some_and(|v| v == "json") {
                    continue;
                }
                match retry(||read_mutation(&path)) {
                    Ok(mutation) => batch.mutations.push(mutation),
                    Err(_) => batch.incidents.push(Incident {
                        id: format!("lecture:{}",path.file_name().unwrap_or_default().to_string_lossy()),
                        kind:"lecture_incomplete".into(),message:"Une écriture n’est pas encore entièrement lisible. Messenger la relira.".into(),message_id:None
                    }),
                }
            }
        }
        for reference in attachments {
            let path = self.root().join("attachments").join(&reference.fingerprint);
            let bytes = retry(|| {
                let bytes = fs::read(&path).map_err(location_error)?;
                verify_attachment(reference, &bytes)?;
                Ok(bytes)
            });
            if let Ok(bytes) = bytes {
                batch
                    .attachments
                    .insert(reference.fingerprint.clone(), bytes);
            }
        }
        batch.checkpoints = self.checkpoints()?;
        Ok(batch)
    }

    fn listen(&self) -> Result<tokio::sync::watch::Receiver<u64>, PortError> {
        let mut current = self.watcher.lock().expect("watcher lock");
        if self.watcher_failed.swap(false, Ordering::Relaxed) {
            *current = None;
        }
        if current.is_none() {
            let changes = self.changes.clone();
            let watcher_failed = self.watcher_failed.clone();
            let mut watcher =
                notify::recommended_watcher(move |result: notify::Result<notify::Event>| {
                    match result {
                        Ok(event)
                            if event.paths.iter().any(|p| {
                                !p.to_string_lossy().contains(".tmp")
                                    && !p.components().any(|c| c.as_os_str() == "installations")
                                    && p.file_name().is_none_or(|n| n != ".messenger.lock")
                            }) =>
                        {
                            changes.send_modify(|value| *value += 1)
                        }
                        Err(_) => {
                            watcher_failed.store(true, Ordering::Relaxed);
                            changes.send_modify(|value| *value += 1);
                        }
                        _ => {}
                    }
                })
                .map_err(|_| PortError("ecoute_indisponible".into()))?;
            watcher
                .watch(&self.root(), RecursiveMode::Recursive)
                .map_err(|_| PortError("ecoute_indisponible".into()))?;
            *current = Some(watcher);
        }
        Ok(self.changes.subscribe())
    }
}

pub fn read_mutation(path: &Path) -> Result<Mutation, PortError> {
    let bytes = fs::read(path).map_err(location_error)?;
    if let Ok(envelope) = serde_json::from_slice::<Envelope>(&bytes) {
        let bytes = serde_json::to_vec(&envelope.mutation).map_err(invalid_record)?;
        if fingerprint(&bytes) == envelope.fingerprint
            || fingerprint(&canonical_bytes(&envelope.mutation).map_err(invalid_record)?)
                == envelope.fingerprint
        {
            return Ok(envelope.mutation);
        }
        return Err(PortError("lecture_incomplete".into()));
    }
    // Compatibility with the already delivered v0.1 exchange envelopes.
    let value: serde_json::Value = serde_json::from_slice(&bytes).map_err(invalid_record)?;
    let filename = path.file_name().unwrap_or_default().to_string_lossy();
    let kind = [
        "message",
        "marking",
        "approval",
        "verdict",
        "reorientation",
        "closure",
    ]
    .into_iter()
    .find(|kind| filename.starts_with(&format!("{kind}-")))
    .ok_or_else(|| PortError("lecture_incomplete".into()))?;
    let mutation: Mutation =
        serde_json::from_value(serde_json::json!({"kind":kind,"payload":value["mutation"]}))
            .map_err(invalid_record)?;
    let raw = match &mutation {
        Mutation::Message(v) => serde_json::to_vec(v),
        Mutation::Marking(v) => serde_json::to_vec(v),
        Mutation::Approval(v) => serde_json::to_vec(v),
        Mutation::Verdict(v) => serde_json::to_vec(v),
        Mutation::Reorientation(v) => serde_json::to_vec(v),
        Mutation::Closure(v) => serde_json::to_vec(v),
        _ => return Err(PortError("lecture_incomplete".into())),
    }
    .map_err(invalid_record)?;
    if value["fingerprint"].as_str() != Some(&fingerprint(&raw)) {
        return Err(PortError("lecture_incomplete".into()));
    }
    Ok(mutation)
}

pub fn fingerprint(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

pub fn verify_attachment(reference: &Attachment, bytes: &[u8]) -> Result<(), PortError> {
    if !Attachment::safe_name(&reference.name)
        || reference.fingerprint.len() != 64
        || !reference.fingerprint.bytes().all(|b| b.is_ascii_hexdigit())
        || reference.size != bytes.len() as u64
        || fingerprint(bytes) != reference.fingerprint
    {
        return Err(PortError("piece_jointe_incomplete".into()));
    }
    Ok(())
}

pub fn atomic_replace(path: &Path, bytes: &[u8]) -> Result<(), PortError> {
    let parent = path
        .parent()
        .ok_or_else(|| PortError("depot_refuse".into()))?;
    fs::create_dir_all(parent).map_err(location_error)?;
    let temporary = parent.join(format!(".{}.tmp", uuid::Uuid::new_v4()));
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&temporary)
        .map_err(location_error)?;
    file.write_all(bytes)
        .and_then(|_| file.sync_all())
        .map_err(location_error)?;
    fs::rename(&temporary, path).map_err(location_error)
}

fn same_or_conflict(path: &Path, expected: &[u8]) -> Result<(), PortError> {
    if fs::read(path).map_err(location_error)? == expected {
        Ok(())
    } else if let Ok(envelope) = serde_json::from_slice::<Envelope>(expected) {
        if read_mutation(path)? == envelope.mutation {
            Ok(())
        } else {
            Err(PortError("mutation_en_conflit".into()))
        }
    } else {
        Err(PortError("mutation_en_conflit".into()))
    }
}

fn retry<T>(mut operation: impl FnMut() -> Result<T, PortError>) -> Result<T, PortError> {
    let mut last = PortError("depot_refuse".into());
    for delay in [0, 120, 280, 600] {
        if delay > 0 {
            thread::sleep(Duration::from_millis(delay));
        }
        match operation() {
            Ok(value) => return Ok(value),
            Err(error) => {
                if error.0 == "mutation_en_conflit" {
                    return Err(error);
                }
                last = error;
            }
        }
    }
    Err(last)
}

fn validate_id(id: &str) -> Result<(), PortError> {
    if !crate::domain::models::safe_id(id) {
        Err(PortError("identifiant_invalide".into()))
    } else {
        Ok(())
    }
}

fn valid_day(day: &str) -> bool {
    NaiveDate::parse_from_str(day, "%Y-%m-%d").is_ok()
}

fn scan_days(root: &Path, since: Option<&str>) -> Result<Vec<PathBuf>, PortError> {
    let Some(start) = since
        .and_then(|value| NaiveDate::parse_from_str(value, "%Y-%m-%d").ok())
        .map(|day| day - Days::days(7))
    else {
        let mut days = Vec::new();
        for year in directories(root)? {
            for month in directories(&year)? {
                for day in directories(&month)? {
                    if day.strip_prefix(root).ok().is_some_and(|relative| {
                        valid_day(&relative.to_string_lossy().replace(['/', '\\'], "-"))
                    }) {
                        days.push(day);
                    }
                }
            }
        }
        days.sort();
        return Ok(days);
    };
    let end = Utc::now().date_naive();
    let mut days = Vec::new();
    for day in start.iter_days().take_while(|day| *day <= end) {
        let path = root.join(format!(
            "{:04}/{:02}/{:02}",
            day.year(),
            day.month(),
            day.day()
        ));
        if path.is_dir() {
            days.push(path);
        }
    }
    Ok(days)
}

fn directories(path: &Path) -> Result<Vec<PathBuf>, PortError> {
    Ok(fs::read_dir(path)
        .map_err(location_error)?
        .filter_map(Result::ok)
        .filter(|entry| {
            entry
                .file_name()
                .to_string_lossy()
                .bytes()
                .all(|b| b.is_ascii_digit())
        })
        .map(|entry| entry.path())
        .filter(|path| path.is_dir())
        .collect())
}

fn location_error(error: std::io::Error) -> PortError {
    PortError(
        if matches!(
            error.kind(),
            std::io::ErrorKind::NotFound | std::io::ErrorKind::NotConnected
        ) {
            "emplacement_injoignable"
        } else {
            "depot_refuse"
        }
        .into(),
    )
}
fn invalid_record(_: serde_json::Error) -> PortError {
    PortError("lecture_incomplete".into())
}

#[cfg(test)]
#[path = "exchange_tests.rs"]
mod tests;
