use crate::{
    domain::{journal::*, models::Attachment, ports::{ExchangePort, PortError}},
    exchange::{fingerprint, verify_attachment},
    retention::RetentionPreview,
};
use reqwest::{blocking::Client, Method, StatusCode, Url};
use serde::{de::DeserializeOwned, Deserialize};
use std::{sync::{mpsc, Arc}, thread, time::Duration};

#[derive(Clone)]
pub struct RemoteExchange {
    url: Arc<str>,
    requests: mpsc::Sender<Request>,
}

struct Request {
    method: Method,
    path: String,
    query: Vec<(String, String)>,
    body: Option<Vec<u8>>,
    json: bool,
    reply: mpsc::SyncSender<Result<Vec<u8>, PortError>>,
}

#[derive(Deserialize)]
struct Receipt { fingerprint: String }
#[derive(Deserialize)]
pub struct Health { pub reachable: bool, pub atomic_publication: bool, pub version: u8 }

pub fn normalize_url(value: &str) -> Result<String, PortError> {
    let url = Url::parse(value.trim()).map_err(|_| PortError("url_invalide".into()))?;
    if url.scheme() != "https" || url.host_str().is_none() || url.username() != "" || url.password().is_some()
        || !matches!(url.path(), "" | "/") || url.query().is_some() || url.fragment().is_some()
    { return Err(PortError("url_https_invalide".into())); }
    Ok(url.as_str().trim_end_matches('/').to_owned())
}

impl RemoteExchange {
    pub fn new(url: &str, token: String) -> Result<Self, PortError> {
        let url = normalize_url(url)?;
        Self::from_url(url, token)
    }
    fn from_url(url: String, token: String) -> Result<Self, PortError> {
        if token.len() < 48 || !token.bytes().all(|byte| byte.is_ascii_alphanumeric()) {
            return Err(PortError("cle_boite_invalide".into()));
        }
        let (requests, incoming) = mpsc::channel::<Request>();
        let base = url.clone();
        thread::Builder::new().name("messenger-https".into()).spawn(move || {
            let Ok(client) = Client::builder().redirect(reqwest::redirect::Policy::none()).build() else { return; };
            for request in incoming {
                let client = client.clone();
                let base = base.clone();
                let token = token.clone();
                thread::spawn(move || {
                    let answer = (|| {
                    let timeout = if request.path == "/v1/health" || request.path == "/v1/probe" { 5 }
                        else if request.path.starts_with("/v1/attachments") { 120 } else { 15 };
                    let mut builder = client.request(request.method, format!("{}{}", base, request.path))
                        .bearer_auth(&token)
                        .timeout(Duration::from_secs(timeout));
                    if !request.query.is_empty() { builder = builder.query(&request.query); }
                    if let Some(body) = request.body {
                        if request.json { builder = builder.header("Content-Type", "application/json"); }
                        builder = builder.body(body);
                    }
                    let response = builder.send().map_err(|_| PortError("emplacement_injoignable".into()))?;
                    let status = response.status();
                    let bytes = response.bytes().map_err(|_| PortError("lecture_incomplete".into()))?;
                    if !status.is_success() {
                        if status == StatusCode::UNAUTHORIZED { return Err(PortError("acces_refuse".into())); }
                        if status == StatusCode::NOT_FOUND { return Err(PortError("piece_jointe_incomplete".into())); }
                        let code = serde_json::from_slice::<serde_json::Value>(&bytes).ok()
                            .and_then(|value| value["error"].as_str().map(str::to_owned))
                            .unwrap_or_else(|| "emplacement_injoignable".into());
                        return Err(PortError(code));
                    }
                    Ok(bytes.to_vec())
                    })();
                    let _ = request.reply.send(answer);
                });
            }
        }).map_err(|_| PortError("emplacement_injoignable".into()))?;
        Ok(Self { url: url.into(), requests })
    }

    pub fn url(&self) -> &str { &self.url }
    fn send(&self, method: Method, path: &str, query: Vec<(String, String)>, body: Option<Vec<u8>>, json: bool) -> Result<Vec<u8>, PortError> {
        let (reply, result) = mpsc::sync_channel(1);
        self.requests.send(Request { method, path: path.into(), query, body, json, reply })
            .map_err(|_| PortError("emplacement_injoignable".into()))?;
        result.recv().map_err(|_| PortError("emplacement_injoignable".into()))?
    }
    fn decode<T: DeserializeOwned>(&self, method: Method, path: &str, query: Vec<(String, String)>, body: Option<Vec<u8>>, json: bool) -> Result<T, PortError> {
        serde_json::from_slice(&self.send(method, path, query, body, json)?)
            .map_err(|_| PortError("lecture_incomplete".into()))
    }
    pub fn health(&self) -> Result<Health, PortError> {
        let health: Health = self.decode(Method::GET, "/v1/health", Vec::new(), None, false)?;
        if health.version != 1 { return Err(PortError("version_boite_incompatible".into())); }
        Ok(health)
    }
    pub fn probe(&self) -> Result<(), PortError> {
        self.send(Method::POST, "/v1/probe", Vec::new(), None, false).map(|_| ())
    }
    pub fn retention_preview(&self) -> Result<RetentionPreview, PortError> {
        self.decode(Method::GET, "/v1/retention", Vec::new(), None, false)
    }
    pub fn retention_apply(&self, fingerprint: &str, installation: &str) -> Result<RetentionPreview, PortError> {
        let body = serde_json::to_vec(&serde_json::json!({"fingerprint":fingerprint,"installation":installation}))
            .map_err(|_| PortError("depot_refuse".into()))?;
        self.decode(Method::POST, "/v1/retention", Vec::new(), Some(body), true)
    }
}

impl ExchangePort for RemoteExchange {
    fn deposit(&self, item: ExchangeItem<'_>) -> Result<String, PortError> {
        let (method, path, query, body, json, expected) = match item {
            ExchangeItem::Mutation(value) => {
                let body = serde_json::to_vec(value).map_err(|_| PortError("depot_refuse".into()))?;
                let proof = fingerprint(&canonical_bytes(value).map_err(|_| PortError("depot_refuse".into()))?);
                (Method::POST, "/v1/mutations", Vec::new(), body, true, proof)
            }
            ExchangeItem::Attachment { reference, bytes } => {
                verify_attachment(reference, bytes)?;
                (Method::POST, "/v1/attachments", vec![("name".into(), reference.name.clone()), ("fingerprint".into(), reference.fingerprint.clone()), ("size".into(), reference.size.to_string())], bytes.to_vec(), false, reference.fingerprint.clone())
            }
            ExchangeItem::Checkpoint(value) => {
                let body = serde_json::to_vec(value).map_err(|_| PortError("depot_refuse".into()))?;
                let proof = fingerprint(&body);
                (Method::PUT, "/v1/checkpoints", Vec::new(), body, true, proof)
            }
        };
        let mut last = PortError("emplacement_injoignable".into());
        for delay in [0, 120, 280, 600] {
            if delay > 0 { thread::sleep(Duration::from_millis(delay)); }
            match self.decode::<Receipt>(method.clone(), path, query.clone(), Some(body.clone()), json) {
                Ok(receipt) if receipt.fingerprint == expected => return Ok(expected),
                Ok(_) => return Err(PortError("lecture_incomplete".into())),
                Err(error) if matches!(error.0.as_str(), "mutation_en_conflit" | "piece_jointe_incomplete" | "acces_refuse") => return Err(error),
                Err(error) => last = error,
            }
        }
        Err(last)
    }
    fn list(&self, since: Option<&str>, attachments: &[Attachment]) -> Result<ExchangeBatch, PortError> {
        let query = since.map(|day| vec![("since".into(), day.into())]).unwrap_or_default();
        let mut batch: ExchangeBatch = self.decode(Method::GET, "/v1/list", query, None, false)?;
        for reference in attachments {
            let query = vec![("name".into(), reference.name.clone()), ("fingerprint".into(), reference.fingerprint.clone()), ("size".into(), reference.size.to_string())];
            match self.send(Method::GET, &format!("/v1/attachments/{}", reference.fingerprint), query, None, false) {
                Ok(bytes) if verify_attachment(reference, &bytes).is_ok() => { batch.attachments.insert(reference.fingerprint.clone(), bytes); }
                Err(error) if error.0 == "acces_refuse" => return Err(error),
                _ => {},
            }
        }
        Ok(batch)
    }
    fn listen(&self) -> Result<tokio::sync::watch::Receiver<u64>, PortError> {
        Err(PortError("ecoute_indisponible".into()))
    }
}

#[cfg(test)]
mod tests {
    use super::{normalize_url, RemoteExchange};
    use crate::{domain::{journal::{ExchangeItem, Mutation, ReadCheckpoint}, models::Attachment, ports::ExchangePort}, exchange::fingerprint, test_support::message};
    #[test]
    fn only_root_https_urls_without_embedded_credentials_are_accepted() {
        assert_eq!(normalize_url("https://messenger.arka-squad.app/").unwrap(), "https://messenger.arka-squad.app");
        for url in ["http://messenger.arka-squad.app", "https://user:secret@messenger.arka-squad.app", "https://messenger.arka-squad.app/other", "https://messenger.arka-squad.app?token=secret", "file:///tmp/mail"] {
            assert!(normalize_url(url).is_err(), "{url}");
        }
    }
    #[test]
    #[ignore = "requires an isolated local messenger-server endpoint"]
    fn http_end_to_end_preserves_deposit_proof_and_readback() {
        let url = std::env::var("MESSENGER_REMOTE_TEST_URL").unwrap();
        let token = std::env::var("MESSENGER_REMOTE_TEST_TOKEN").unwrap();
        let remote = RemoteExchange::from_url(url, token).unwrap();
        assert!(remote.health().unwrap().reachable);
        remote.probe().unwrap();
        let id = uuid::Uuid::new_v4().to_string();
        let value = Mutation::Message(message(&id, "a@test", "b@test"));
        let proof = remote.deposit(ExchangeItem::Mutation(&value)).unwrap();
        assert_eq!(remote.deposit(ExchangeItem::Mutation(&value)).unwrap(), proof);
        let mut changed = message(&id, "a@test", "b@test");
        changed.subject = "Conflit".into();
        assert_eq!(remote.deposit(ExchangeItem::Mutation(&Mutation::Message(changed))).unwrap_err().0, "mutation_en_conflit");
        let bytes = b"remote attachment proof";
        let reference = Attachment { name: "proof.txt".into(), fingerprint: fingerprint(bytes), size: bytes.len() as u64 };
        assert_eq!(remote.deposit(ExchangeItem::Attachment { reference: &reference, bytes }).unwrap(), reference.fingerprint);
        let checkpoint = ReadCheckpoint { id: format!("installation-{id}"), machine: "test".into(), seen_at: chrono::Utc::now().to_rfc3339(), integrated: Default::default(), missed_before: None };
        remote.deposit(ExchangeItem::Checkpoint(&checkpoint)).unwrap();
        let batch = remote.list(None, &[reference.clone()]).unwrap();
        assert!(batch.mutations.contains(&value));
        assert_eq!(batch.attachments[&reference.fingerprint], bytes);
        assert!(batch.checkpoints.contains(&checkpoint));
        assert_eq!(remote.retention_preview().unwrap().mutations, 0);
    }
    #[test]
    #[ignore = "requires the new production box URL and its private token"]
    fn https_production_box_accepts_authenticated_read_and_probe() {
        let url = std::env::var("MESSENGER_REMOTE_TEST_URL").unwrap();
        let token = std::env::var("MESSENGER_REMOTE_TEST_TOKEN").unwrap();
        let remote = RemoteExchange::new(&url, token).unwrap();
        assert!(remote.health().unwrap().reachable);
        remote.probe().unwrap();
        let batch = remote.list(None, &[]).unwrap();
        assert!(batch.mutations.is_empty());
        assert!(batch.checkpoints.is_empty());
    }
}
