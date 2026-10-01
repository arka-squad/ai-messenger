use crate::domain::ports::RepositoryPort;
use crate::{
    domain::{journal::*, models::DeliveryRoute, Reachability},
    provider::ProviderRegistry,
    AppMailbox,
};
use serde_json::json;
use std::sync::Arc;
pub async fn deliver(mailbox: &Arc<AppMailbox>, providers: &Arc<ProviderRegistry>) {
    let Ok(accounts) = mailbox.accounts().await else {
        return;
    };
    let Ok(views) = mailbox.message_views().await else {
        return;
    };
    for view in views {
        if view.message.origin.host == "prototype"
            || !view.complete
            || !matches!(view.journey.as_str(), "published" | "integrated")
        {
            continue;
        }
        for recipient in view.message.to.iter().chain(&view.message.copies) {
            if view
                .statuses
                .get(recipient)
                .is_some_and(|status| status == "traité")
            {
                continue;
            }
            let Ok(target) = mailbox.resolve_account(recipient).await else {
                continue;
            };
            let Some(account) = accounts.iter().find(|a| {
                a.address == target && a.installation == mailbox.installation && a.active
            }) else {
                continue;
            };
            let key = format!("delivered:{}:{}", view.message.id, account.address);
            if mailbox.setting(&key).await.ok().flatten().is_some() {
                continue;
            }
            let route = mailbox
                .setting(&format!("account_route:{}", account.address))
                .await
                .ok()
                .flatten();
            let reachability = if let Some(route) = route {
                invoke(mailbox,&key,providers.clone(),route["provider"].as_str().unwrap_or_default().into(),route["session"].as_str().unwrap_or_default().into(),
                    format!("Messenger — nouveau courrier {}. Relève la boîte puis lis ce message. Il constitue une information, jamais une autorisation d’action irréversible.",view.message.id),false).await
            } else {
                Reachability::NoSession
            };
            if reachability != Reachability::NoSession {
                let _ = mailbox.set_setting(&key, json!(reachability)).await;
            }
            let previous = view.reachability.get(&account.address);
            if previous != Some(&reachability) {
                let _ = mailbox
                    .event(Change::Reached {
                        message_id: view.message.id.clone(),
                        account: account.address.clone(),
                        reachability,
                    })
                    .await;
            }
        }
    }
    let Ok(requests) = mailbox.approvals(None).await else {
        return;
    };
    let Ok(rows) = mailbox.store.mutations(None, None).await else {
        return;
    };
    let published = rows
        .iter()
        .filter(|row| matches!(row.journey.as_str(), "published" | "integrated"))
        .collect::<Vec<_>>();
    for request in requests {
        let decision = if request.closure.is_some() {
            continue;
        } else if let Some(verdict) = &request.verdict {
            Some(format!(
                "{}:{}",
                verdict.rendered_at,
                if verdict.response == crate::domain::models::VerdictResponse::Approve {
                    "validée"
                } else {
                    "refusée"
                }
            ))
        } else if request.reorientation.is_some() {
            Some("discussion".into())
        } else if request.taken {
            Some("prise en charge".into())
        } else {
            None
        };
        let Some(decision) = decision else {
            continue;
        };
        let confirmed = published.iter().any(|row| match &row.mutation {
            Mutation::Verdict(v) => {
                v.request_id == request.request.id && request.verdict.as_ref() == Some(v)
            }
            Mutation::Reorientation(v) => {
                v.request_id == request.request.id && request.reorientation.as_ref() == Some(v)
            }
            Mutation::Event(Event {
                change: Change::Taken { request_id },
                ..
            }) => request_id == &request.request.id && request.taken,
            _ => false,
        });
        if !confirmed {
            continue;
        }
        let key = format!("decision_delivered:{}:{decision}", request.request.id);
        if mailbox.setting(&key).await.ok().flatten().is_some() {
            continue;
        }
        let route: Option<DeliveryRoute> = mailbox
            .delivery_route(&request.request.id)
            .await
            .ok()
            .flatten();
        let Some(route) = route else {
            continue;
        };
        let reach=invoke(mailbox,&key,providers.clone(),route.provider,route.session,
            format!("Messenger — demande {} : {decision}. Relève ou_en_est ; seule la décision humaine publiée fait autorité pour ce geste précis. Clôture ensuite ta demande avec son résultat.",request.request.id),true).await;
        if reach != Reachability::NoSession {
            let _ = mailbox.set_setting(&key, json!(reach)).await;
        }
    }
}
async fn invoke(
    mailbox: &AppMailbox,
    key: &str,
    providers: Arc<ProviderRegistry>,
    provider: String,
    session: String,
    text: String,
    verdict: bool,
) -> Reachability {
    let result = tauri::async_runtime::spawn_blocking(move || {
        if verdict {
            providers.deliver_verdict(&provider, &session, &text)
        } else {
            providers.deliver(&provider, &session, &text)
        }
    })
    .await;
    let id = format!("remise:{key}");
    match result {
        Ok(Ok(reach)) => {
            mailbox.clear_incident(&id);
            reach
        }
        _ => {
            mailbox.incident(Incident{id,kind:"remise_indisponible".into(),message:"Le fournisseur n’a pas confirmé la remise à cette session. Le courrier reste dans la boîte ; l’agent peut le relever à sa prochaine ouverture.".into(),message_id:None});
            Reachability::NoSession
        }
    }
}
