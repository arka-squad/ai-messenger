#![allow(dead_code)]

#[path = "../../src-tauri/src/domain.rs"]
mod domain;
#[path = "../../src-tauri/src/exchange.rs"]
mod exchange;
#[path = "../../src-tauri/src/retention.rs"]
mod retention;

mod mailbox {
    pub fn hash(bytes: &[u8]) -> String { crate::exchange::fingerprint(bytes) }
    pub fn new_id() -> String { uuid::Uuid::new_v4().to_string() }
    pub fn now() -> String { chrono::Utc::now().to_rfc3339() }
}

use axum::{
    body::Bytes,
    extract::{DefaultBodyLimit, Path, Query, State},
    http::{header::AUTHORIZATION, StatusCode},
    middleware::{self, Next},
    response::{IntoResponse, Response},
    routing::{get, post, put},
    Json, Router,
};
use domain::{journal::{ExchangeBatch, ExchangeItem, Mutation, ReadCheckpoint}, models::Attachment, ports::{ExchangePort, PortError}};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::{fs, path::PathBuf, sync::Arc};

#[derive(Clone)]
struct Service {
    exchange: exchange::DirectoryExchange,
    token: Arc<str>,
}

struct ApiError(PortError);
impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        let code = match self.0.0.as_str() {
            "mutation_en_conflit" | "apercu_conservation_modifie" => StatusCode::CONFLICT,
            "identifiant_invalide" | "piece_jointe_incomplete" => StatusCode::UNPROCESSABLE_ENTITY,
            "emplacement_injoignable" | "boite_occupee" | "lecture_incomplete" => StatusCode::SERVICE_UNAVAILABLE,
            _ => StatusCode::BAD_REQUEST,
        };
        (code, Json(json!({"error": self.0.0}))).into_response()
    }
}
type Result<T> = std::result::Result<T, ApiError>;
impl From<PortError> for ApiError { fn from(error: PortError) -> Self { Self(error) } }

async fn blocking<T: Send + 'static>(f: impl FnOnce() -> std::result::Result<T, PortError> + Send + 'static) -> Result<T> {
    tokio::task::spawn_blocking(f).await.map_err(|_| ApiError(PortError("operation_interrompue".into())))?.map_err(Into::into)
}

fn secret_matches(actual: &[u8], expected: &[u8]) -> bool {
    if actual.len() != expected.len() { return false; }
    actual.iter().zip(expected).fold(0u8, |diff, (a,b)| diff | (a ^ b)) == 0
}

async fn authorize(State(service): State<Service>, request: axum::extract::Request, next: Next) -> Response {
    let expected = format!("Bearer {}", service.token);
    let actual = request.headers().get(AUTHORIZATION).map(|value| value.as_bytes()).unwrap_or_default();
    if !secret_matches(actual, expected.as_bytes()) { return StatusCode::UNAUTHORIZED.into_response(); }
    next.run(request).await
}

#[derive(Serialize)]
struct Health { version: u8, reachable: bool, atomic_publication: bool }
async fn health(State(service): State<Service>) -> Json<Health> {
    Json(Health { version: 1, reachable: service.exchange.reachable(), atomic_publication: service.exchange.atomic_publication() })
}

async fn probe(State(service): State<Service>) -> Result<StatusCode> {
    blocking(move || {
        let path = service.exchange.root().join(format!(".probe-{}.tmp", uuid::Uuid::new_v4()));
        let outcome = (|| {
            use std::io::Write;
            let mut file = fs::OpenOptions::new().write(true).create_new(true).open(&path).map_err(|_| PortError("depot_refuse".into()))?;
            file.write_all(b"messenger").and_then(|_| file.sync_all()).map_err(|_| PortError("depot_refuse".into()))?;
            if fs::read(&path).map_err(|_| PortError("lecture_incomplete".into()))? != b"messenger" { return Err(PortError("lecture_incomplete".into())); }
            Ok(())
        })();
        let _ = fs::remove_file(path);
        outcome
    }).await?;
    Ok(StatusCode::NO_CONTENT)
}

#[derive(Serialize)]
struct Receipt { fingerprint: String }
async fn mutation(State(service): State<Service>, Json(value): Json<Mutation>) -> Result<Json<Receipt>> {
    let proof = blocking(move || service.exchange.deposit(ExchangeItem::Mutation(&value))).await?;
    Ok(Json(Receipt { fingerprint: proof }))
}
async fn attachment(State(service): State<Service>, Query(reference): Query<Attachment>, body: Bytes) -> Result<Json<Receipt>> {
    let proof = blocking(move || service.exchange.deposit(ExchangeItem::Attachment { reference: &reference, bytes: &body })).await?;
    Ok(Json(Receipt { fingerprint: proof }))
}
async fn checkpoint(State(service): State<Service>, Json(value): Json<ReadCheckpoint>) -> Result<Json<Receipt>> {
    let proof = blocking(move || service.exchange.deposit(ExchangeItem::Checkpoint(&value))).await?;
    Ok(Json(Receipt { fingerprint: proof }))
}

#[derive(Deserialize)]
struct ListQuery { since: Option<String> }
async fn list(State(service): State<Service>, Query(query): Query<ListQuery>) -> Result<Json<ExchangeBatch>> {
    if query.since.as_deref().is_some_and(|date| chrono::NaiveDate::parse_from_str(date, "%Y-%m-%d").is_err()) {
        return Err(ApiError(PortError("date_invalide".into())));
    }
    let result = blocking(move || service.exchange.list(query.since.as_deref(), &[])).await?;
    Ok(Json(result))
}
async fn read_attachment(State(service): State<Service>, Path(hash): Path<String>, Query(reference): Query<Attachment>) -> Result<Bytes> {
    if hash != reference.fingerprint || hash.len() != 64 || !hash.bytes().all(|byte| byte.is_ascii_hexdigit()) {
        return Err(ApiError(PortError("piece_jointe_incomplete".into())));
    }
    let data = blocking(move || {
        let _gate = service.exchange.gate(false)?;
        let bytes = fs::read(service.exchange.root().join("attachments").join(hash)).map_err(|_| PortError("piece_jointe_incomplete".into()))?;
        exchange::verify_attachment(&reference, &bytes)?;
        Ok(bytes)
    }).await?;
    Ok(Bytes::from(data))
}

async fn retention_preview(State(service): State<Service>) -> Result<Json<retention::RetentionPreview>> {
    let result = blocking(move || retention::preview(&service.exchange)).await?;
    Ok(Json(result))
}
#[derive(Deserialize)]
struct RetentionApply { fingerprint: String, installation: String }
async fn retention_apply(State(service): State<Service>, Json(request): Json<RetentionApply>) -> Result<Json<retention::RetentionPreview>> {
    if !domain::models::safe_id(&request.installation) {
        return Err(ApiError(PortError("identifiant_invalide".into())));
    }
    let result = blocking(move || retention::apply(&service.exchange, &request.fingerprint, &request.installation)).await?;
    Ok(Json(result))
}

fn router(service: Service) -> Router {
    Router::new()
        .route("/v1/health", get(health))
        .route("/v1/probe", post(probe))
        .route("/v1/mutations", post(mutation))
        .route("/v1/attachments", post(attachment))
        .route("/v1/attachments/{hash}", get(read_attachment))
        .route("/v1/checkpoints", put(checkpoint))
        .route("/v1/list", get(list))
        .route("/v1/retention", get(retention_preview).post(retention_apply))
        .layer(DefaultBodyLimit::disable())
        .route_layer(middleware::from_fn_with_state(service.clone(), authorize))
        .with_state(service)
}

fn main() -> std::result::Result<(), Box<dyn std::error::Error>> {
    let root = PathBuf::from(std::env::var("MESSENGER_ROOT")?);
    if !root.is_dir() { return Err("La boîte serveur est absente".into()); }
    let token = fs::read_to_string(std::env::var("MESSENGER_TOKEN_FILE")?)?.trim().to_owned();
    if token.len() < 48 || !token.bytes().all(|byte| byte.is_ascii_alphanumeric()) { return Err("Clé serveur invalide".into()); }
    let service = Service { exchange: exchange::DirectoryExchange::new(root), token: token.into() };
    let runtime = tokio::runtime::Builder::new_multi_thread().enable_all().build()?;
    runtime.block_on(async {
        let address = std::env::var("MESSENGER_LISTEN_ADDR").unwrap_or_else(|_| "0.0.0.0:8080".into());
        let listener = tokio::net::TcpListener::bind(address).await?;
        axum::serve(listener, router(service)).await?;
        Ok(())
    })
}
