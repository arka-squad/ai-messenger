mod app_exchange;
mod delivery;
#[allow(dead_code)]
mod domain;
mod exchange;
mod mailbox;
mod mcp;
mod migration;
mod notifications;
mod owner_commands;
mod provider;
mod remote_exchange;
mod retention;
mod storage;
#[cfg(test)]
mod test_support;

use std::{
    collections::BTreeMap,
    fs,
    io::Write,
    path::{Path, PathBuf},
    sync::Arc,
    time::Duration,
};

use domain::{
    models::{MailMessage, ProviderStatus, Reorientation, Verdict, VerdictResponse},
    Reachability,
};
use app_exchange::AppExchange;
use exchange::DirectoryExchange;
use mailbox::{ApprovalView, MailboxService};
use provider::ProviderRegistry;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use storage::LocalStore;
use tauri::Manager;

type AppMailbox = MailboxService<LocalStore, AppExchange>;

struct AppState {
    mailbox: Arc<AppMailbox>,
    providers: Arc<ProviderRegistry>,
    exchange: AppExchange,
    exchange_location_file: PathBuf,
    installation: String,
}

#[derive(Serialize)]
struct AppHealth {
    schema_version: u8,
}

#[derive(Serialize)]
struct ExchangeLocation {
    path: String,
    kind: &'static str,
    configured: bool,
    reachable: bool,
    listening: bool,
    interval_seconds: u8,
    atomic_publication: bool,
}

#[tauri::command]
async fn app_health(state: tauri::State<'_, AppState>) -> Result<AppHealth, String> {
    Ok(AppHealth {
        schema_version: state
            .mailbox
            .schema_version()
            .await
            .map_err(|error| error.to_string())?,
    })
}

#[tauri::command]
async fn receive_mail(state: tauri::State<'_, AppState>) -> Result<usize, String> {
    state
        .mailbox
        .receive()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
fn exchange_location(state: tauri::State<'_, AppState>) -> ExchangeLocation {
    exchange_location_value(&state)
}

#[tauri::command]
async fn choose_exchange_location(
    state: tauri::State<'_, AppState>,
    app: tauri::AppHandle,
) -> Result<Option<ExchangeLocation>, String> {
    let selected = tauri::async_runtime::spawn_blocking(|| rfd::FileDialog::new().pick_folder())
        .await
        .map_err(|error| error.to_string())?;
    let Some(path) = selected else {
        return Ok(None);
    };
    verify_exchange_location(&path)?;
    persist_exchange_location(&state.exchange_location_file, &path)
        .map_err(|_| "La boîte n’a pas pu être mémorisée sur cet ordinateur.".to_owned())?;
    app.request_restart();
    Ok(None)
}

#[tauri::command]
async fn choose_exchange_url(url: String, token: String, state: tauri::State<'_, AppState>, app: tauri::AppHandle) -> Result<(), String> {
    let url = remote_exchange::normalize_url(&url).map_err(|error| error.to_string())?;
    let remote = remote_exchange::RemoteExchange::new(&url, token.clone()).map_err(|error| error.to_string())?;
    tauri::async_runtime::spawn_blocking(move || {
        if !remote.health().map_err(|error| error.to_string())?.reachable { return Err("La boîte distante est indisponible.".into()); }
        remote.probe().map_err(|error| error.to_string())
    }).await.map_err(|error| error.to_string())??;
    persist_exchange_token(&state.exchange_location_file, &url, &token)?;
    persist_exchange_location(&state.exchange_location_file, Path::new(&url))
        .map_err(|_| "L’URL de la boîte n’a pas pu être mémorisée.".to_owned())?;
    app.request_restart();
    Ok(())
}

#[tauri::command]
async fn list_mail(state: tauri::State<'_, AppState>) -> Result<Vec<MailMessage>, String> {
    state
        .mailbox
        .messages()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn mail_statuses(
    state: tauri::State<'_, AppState>,
) -> Result<BTreeMap<String, BTreeMap<String, String>>, String> {
    state
        .mailbox
        .statuses()
        .await
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn list_approvals(state: tauri::State<'_, AppState>) -> Result<Vec<ApprovalView>, String> {
    state
        .mailbox
        .approvals(None)
        .await
        .map_err(|error| error.to_string())
}

#[derive(Deserialize)]
struct VerdictInput {
    request_id: String,
    response: String,
    rendered_at: String,
    note: Option<String>,
}

#[derive(Serialize)]
struct AnswerOutcome {
    publication: String,
    reachability: Option<Reachability>,
    notice: Option<String>,
}

#[tauri::command]
fn provider_statuses(state: tauri::State<'_, AppState>) -> Vec<ProviderStatus> {
    state.providers.statuses()
}

#[tauri::command]
async fn equip_provider(
    id: String,
    state: tauri::State<'_, AppState>,
) -> Result<ProviderStatus, String> {
    let providers = state.providers.clone();
    tauri::async_runtime::spawn_blocking(move || providers.equip(&id))
        .await
        .map_err(|error| error.to_string())?
        .map_err(|error| error.to_string())
}

#[tauri::command]
async fn answer_approval(
    verdict: VerdictInput,
    state: tauri::State<'_, AppState>,
) -> Result<AnswerOutcome, String> {
    let request_id = verdict.request_id.clone();
    let response = match verdict.response.as_str() {
        "valider" => Some(VerdictResponse::Approve),
        "refuser" => Some(VerdictResponse::Refuse),
        "discuter" => None,
        "prendre_en_charge" => {
            let publication = state
                .mailbox
                .take_intervention(&verdict.request_id)
                .await
                .map_err(|e| e.to_string())?;
            delivery::deliver(&state.mailbox, &state.providers).await;
            return Ok(AnswerOutcome {
                publication,
                reachability: None,
                notice: Some("Intervention prise en charge. Rejoins la session de l’agent.".into()),
            });
        }
        _ => return Err("unknown approval response".into()),
    };
    let (publication, message, is_verdict) = if let Some(response) = response {
        let publication = state
            .mailbox
            .answer(Verdict {
                request_id: verdict.request_id,
                response,
                rendered_at: verdict.rendered_at,
                rendered_from: state.installation.clone(),
                note: verdict.note,
            })
            .await
            .map_err(|error| error.to_string())?;
        let decision = match response {
            VerdictResponse::Approve => "VALIDÉE",
            VerdictResponse::Refuse => "REFUSÉE",
        };
        (
            publication,
            format!(
                "Messenger — demande {request_id} {decision}. Relève son état, puis clôture-la avec le résultat."
            ),
            true,
        )
    } else {
        let to = state
            .mailbox
            .approvals(None)
            .await
            .map_err(|error| error.to_string())?
            .into_iter()
            .find(|request| request.request.id == verdict.request_id)
            .map(|request| request.request.opened_by)
            .ok_or_else(|| "approval request not found".to_owned())?;
        let publication = state
            .mailbox
            .redirect(Reorientation {
                request_id: verdict.request_id,
                to,
                redirected_at: verdict.rendered_at,
                note: verdict.note,
            })
            .await
            .map_err(|error| error.to_string())?;
        (
            publication,
            format!("Messenger — discussion demandée pour {request_id}. Reprends avec ton humain."),
            false,
        )
    };
    delivery::deliver(&state.mailbox, &state.providers).await;
    let _ = (message, is_verdict);
    let pending = publication == "pending";
    Ok(AnswerOutcome {
        publication,
        reachability: None,
        notice: if pending {
            Some("Décision enregistrée localement, encore en attente de publication. L’agent ne reçoit aucune autorisation avant la confirmation du dépôt.".into())
        } else {
            None
        },
    })
}

fn installation_id(data_dir: &Path) -> std::io::Result<String> {
    let path = data_dir.join("installation-id");
    if let Ok(id) = std::fs::read_to_string(&path) {
        if id.len() == 64 && id.bytes().all(|byte| byte.is_ascii_hexdigit()) {
            return Ok(id);
        }
    }
    let seed = format!(
        "{}:{}:{:?}",
        data_dir.display(),
        std::process::id(),
        std::time::SystemTime::now()
    );
    let id = format!("{:x}", Sha256::digest(seed));
    let temporary = data_dir.join(".installation-id.tmp");
    std::fs::write(&temporary, &id)?;
    std::fs::rename(temporary, path)?;
    Ok(id)
}

fn exchange_location_value(state: &AppState) -> ExchangeLocation {
    let (reachable, atomic_publication) = match &state.exchange {
        AppExchange::Directory(exchange) => (exchange.reachable(), exchange.atomic_publication()),
        AppExchange::Remote(exchange) => exchange.health().map(|status| (status.reachable, status.atomic_publication)).unwrap_or((false, false)),
    };
    ExchangeLocation {
        path: state.exchange.location(),
        kind: state.exchange.kind(),
        configured: state.exchange_location_file.exists(),
        reachable,
        listening: state.exchange.listening(),
        interval_seconds: if state.exchange.listening() { 60 } else { 10 },
        atomic_publication,
    }
}

fn verify_exchange_location(path: &Path) -> Result<(), String> {
    if !path.is_dir() || fs::read_dir(path).is_err() {
        return Err("Ce dossier n’est pas joignable. Connecte-le puis réessaie.".into());
    }
    let probe = path.join(format!(".messenger-access-{}.tmp", uuid::Uuid::new_v4()));
    let result = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&probe)
        .and_then(|mut file| file.write_all(b"messenger"));
    let _ = fs::remove_file(probe);
    result.map_err(|_| "Ce dossier est accessible en lecture, mais pas en écriture.".to_owned())
}

fn persist_exchange_location(file: &Path, location: &Path) -> std::io::Result<()> {
    exchange::atomic_replace(file, location.to_string_lossy().as_bytes())
        .map_err(std::io::Error::other)
}

fn token_path(location_file: &Path, url: &str) -> PathBuf {
    location_file.parent().expect("app data").join("exchange-secrets").join(exchange::fingerprint(url.as_bytes()))
}

fn persist_exchange_token(location_file: &Path, url: &str, token: &str) -> Result<(), String> {
    let path = token_path(location_file, url);
    let parent = path.parent().expect("secret directory");
    fs::create_dir_all(parent).map_err(|_| "La clé de la boîte n’a pas pu être mémorisée.")?;
    #[cfg(unix)]
    fs::set_permissions(parent, std::os::unix::fs::PermissionsExt::from_mode(0o700))
        .map_err(|_| "La clé de la boîte n’a pas pu être protégée.")?;
    let temporary = parent.join(format!(".{}.tmp", uuid::Uuid::new_v4()));
    let mut options = fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    { use std::os::unix::fs::OpenOptionsExt; options.mode(0o600); }
    let mut file = options.open(&temporary).map_err(|_| "La clé de la boîte n’a pas pu être mémorisée.")?;
    file.write_all(token.as_bytes()).and_then(|_| file.sync_all()).map_err(|_| "La clé de la boîte n’a pas pu être mémorisée.")?;
    fs::rename(temporary, path).map_err(|_| "La clé de la boîte n’a pas pu être mémorisée.".into())
}

fn store_path(data_dir: &Path, location: &str) -> Result<PathBuf, Box<dyn std::error::Error>> {
    let legacy = data_dir.join("database");
    let marker = data_dir.join("legacy-exchange-location");
    if legacy.exists() {
        if !marker.exists() { exchange::atomic_replace(&marker, location.as_bytes())?; }
        if fs::read_to_string(&marker)? == location { return Ok(legacy); }
    }
    Ok(data_dir.join("boxes").join(exchange::fingerprint(location.as_bytes())).join("database"))
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_clipboard_manager::init())
        .setup(|app| {
            let data_dir = app.path().app_data_dir()?;
            std::fs::create_dir_all(&data_dir)?;
            let installation = installation_id(&data_dir)?;
            let exchange_location_file = data_dir.join("exchange-location");
            #[cfg(debug_assertions)]
            if let Some(path)=std::env::var_os("MESSENGER_DEV_EXCHANGE") {
                let path=PathBuf::from(path);
                verify_exchange_location(&path)?;
                exchange::atomic_replace(&exchange_location_file,path.to_string_lossy().as_bytes())?;
            }
            let configured_location = fs::read_to_string(&exchange_location_file)
                .ok()
                .filter(|path| !path.trim().is_empty())
                .unwrap_or_else(|| data_dir.join("exchange").to_string_lossy().into_owned());
            let is_remote = configured_location.starts_with("https://");
            if !exchange_location_file.exists() {fs::create_dir_all(&configured_location)?;}
            let database_path = store_path(&data_dir, &configured_location)?;
            fs::create_dir_all(database_path.parent().expect("database parent"))?;
            let store = tauri::async_runtime::block_on(LocalStore::open(database_path))?;
            let exchange = if is_remote {
                let token = fs::read_to_string(token_path(&exchange_location_file, &configured_location))?;
                AppExchange::Remote(remote_exchange::RemoteExchange::new(&configured_location, token)?)
            } else {
                AppExchange::Directory(DirectoryExchange::with_cursor(&configured_location, data_dir.join("exchange-cursors")))
            };
            let machine=std::env::var("COMPUTERNAME").or_else(|_|std::env::var("HOSTNAME")).unwrap_or_else(|_|{
                std::process::Command::new("hostname").output().ok().map(|o|String::from_utf8_lossy(&o.stdout).trim().into()).unwrap_or_else(||"Cet ordinateur".into())
            });
            let mailbox = Arc::new(MailboxService::with_installation(store, exchange.clone(),installation.clone(),machine));
            #[cfg(target_os = "macos")]
            let _ = notify_rust::set_application("app.arkalabs.messenger");
            #[cfg(debug_assertions)]
            if let Some(source)=std::env::var_os("MESSENGER_DEV_IMPORT_SOURCE") {
                let proof=std::env::var("MESSENGER_DEV_IMPORT_FINGERPRINT").map_err(|_|"La copie de développement doit avoir été vérifiée avant sa reprise.")?;
                if tauri::async_runtime::block_on(mailbox.setting("migration_complete"))?.is_none() {
                    tauri::async_runtime::block_on(migration::apply(&mailbox,&PathBuf::from(source),&proof))?;
                }
            }
            let providers = Arc::new(ProviderRegistry::new());
            tauri::async_runtime::spawn(mcp::serve(mailbox.clone()));
            tauri::async_runtime::spawn(provider::serve_claude(mailbox.clone()));
            let poller = mailbox.clone();
            let watched=exchange.clone();
            let delivering=providers.clone();
            let notifying=app.handle().clone();
            tauri::async_runtime::spawn(async move {
                let mut legacy_projects=true;
                loop {
                    let received=poller.receive().await.is_ok() && !poller.incidents().iter().any(|i|i.id=="emplacement");
                    // Projects kept locally by earlier versions are shared once the box has been read.
                    if legacy_projects && received {
                        legacy_projects=false;
                        if let Err(error)=poller.share_legacy_projects().await {
                            eprintln!("Messenger : les projets locaux seront partagés au prochain démarrage ({error}).");
                        }
                    }
                    // Deliveries run beside the relève: a slow provider never holds the box back.
                    let (mailbox,providers)=(poller.clone(),delivering.clone());
                    tauri::async_runtime::spawn(async move{delivery::deliver(&mailbox,&providers).await});
                    notifications::notify(&poller,&notifying).await;
                    use domain::ports::ExchangePort;
                    let mut changes=watched.listen().ok();
                    let interval=if watched.listening() {60} else {10};
                    if let Some(changes)=changes.as_mut() {
                        tokio::select! {_=changes.changed()=>{},_=tokio::time::sleep(Duration::from_secs(interval))=>{}}
                    } else {tokio::time::sleep(Duration::from_secs(interval)).await;}
                }
            });
            app.manage(AppState {
                mailbox,
                providers,
                exchange,
                exchange_location_file,
                installation,
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            app_health,
            receive_mail,
            exchange_location,
            choose_exchange_location,
            choose_exchange_url,
            list_mail,
            mail_statuses,
            list_approvals,
            answer_approval,
            provider_statuses,
            equip_provider,
            owner_commands::snapshot,
            owner_commands::save_preferences,
            owner_commands::create_project,
            owner_commands::copy_invitation,
            owner_commands::update_account,
            owner_commands::set_account_active,
            owner_commands::merge_accounts,
            owner_commands::file_account,
            owner_commands::save_contacts,
            owner_commands::request_attachment,
            owner_commands::save_attachment,
            owner_commands::open_attachment,
            owner_commands::choose_migration_source,
            owner_commands::apply_migration,
            owner_commands::preview_retention,
            owner_commands::apply_retention,
            owner_commands::shutdown,
            owner_commands::watch_projects,
            owner_commands::set_delegates,
            owner_commands::open_observation,
            owner_commands::pause_observation,
            owner_commands::revoke_observation
        ])
        .run(tauri::generate_context!())
        .expect("Messenger could not start");
}

#[cfg(test)]
#[test]
fn changing_box_never_reuses_the_old_local_database() {
    let root = test_support::Temporary::new();
    fs::create_dir(root.0.join("database")).unwrap();
    let local = "/Volumes/old-share";
    assert_eq!(store_path(&root.0, local).unwrap(), root.0.join("database"));
    let online = store_path(&root.0, "https://messenger.arka-squad.app").unwrap();
    assert_ne!(online, root.0.join("database"));
    assert_eq!(store_path(&root.0, local).unwrap(), root.0.join("database"));
}
