use super::*;
use serde::Serialize;

#[derive(Clone, Debug, Serialize)]
pub struct ApprovalView {
    #[serde(flatten)]
    pub request: ApprovalRequest,
    pub verdict: Option<Verdict>,
    pub reorientation: Option<Reorientation>,
    pub closure: Option<RequestClosure>,
    pub taken: bool,
    pub effective_nature: RequestNature,
    pub decision_journey: Option<String>,
    pub closure_journey: Option<String>,
}
impl<R: RepositoryPort, E: ExchangePort> MailboxService<R, E> {
    pub async fn request_approval(&self, request: ApprovalRequest) -> Result<String, MailboxError> {
        let _guard = self.changes.lock().await;
        self.require_account(&request.opened_by).await?;
        validate_request(&request)?;
        self.publish(Mutation::Approval(request)).await
    }
    pub async fn request_approval_from(
        &self,
        request: ApprovalRequest,
        route: DeliveryRoute,
    ) -> Result<String, MailboxError> {
        if request.id != route.request_id || route.provider.is_empty() || route.session.is_empty() {
            return Err(refusal(
                "session_inconnue",
                "Une demande doit connaître sa session de retour.",
            ));
        }
        if let Some(previous) = self.delivery_route(&request.id).await? {
            if previous != route {
                return Err(refusal(
                    "session_de_retour_fixe",
                    "La demande existante conserve sa session de retour d’origine.",
                ));
            }
        }
        self.set_setting(&format!("route:{}", request.id), json!(route))
            .await?;
        self.request_approval(request).await
    }
    pub async fn delivery_route(&self, id: &str) -> Result<Option<DeliveryRoute>, MailboxError> {
        self.setting(&format!("route:{id}"))
            .await?
            .map(serde_json::from_value)
            .transpose()
            .map_err(|_| {
                refusal(
                    "route_invalide",
                    "La session de retour de cette demande est illisible.",
                )
            })
    }
    async fn request_view(&self, id: &str) -> Result<ApprovalView, MailboxError> {
        self.approvals(None)
            .await?
            .into_iter()
            .find(|v| v.request.id == id)
            .ok_or_else(|| {
                refusal(
                    "demande_inconnue",
                    "Cette demande n’existe pas dans la boîte.",
                )
            })
    }
    pub async fn answer(&self, verdict: Verdict) -> Result<String, MailboxError> {
        let _guard = self.changes.lock().await;
        if chrono::DateTime::parse_from_rfc3339(&verdict.rendered_at).is_err() {
            return Err(refusal(
                "decision_invalide",
                "La décision doit avoir une date valide.",
            ));
        }
        let request = self.request_view(&verdict.request_id).await?;
        if request.effective_nature != RequestNature::Validation {
            return Err(refusal(
                "intervention",
                "Cette demande attend une intervention dans la session, pas un verdict.",
            ));
        }
        if request.verdict.is_some() || request.closure.is_some() {
            return Err(refusal(
                "demande_deja_decidee",
                "Une décision a déjà été prise pour cette demande.",
            ));
        }
        validate_note(verdict.note.as_deref())?;
        self.publish(Mutation::Verdict(verdict)).await
    }
    pub async fn redirect(&self, redirect: Reorientation) -> Result<String, MailboxError> {
        let _guard = self.changes.lock().await;
        if chrono::DateTime::parse_from_rfc3339(&redirect.redirected_at).is_err() {
            return Err(refusal(
                "decision_invalide",
                "La réorientation doit avoir une date valide.",
            ));
        }
        let request = self.request_view(&redirect.request_id).await?;
        if request.verdict.is_some()
            || request.reorientation.is_some()
            || request.closure.is_some()
            || request.request.opened_by != redirect.to
        {
            return Err(refusal("reorientation_refusee","La discussion revient uniquement à l’agent ouvrant une demande encore sans décision."));
        }
        validate_note(redirect.note.as_deref())?;
        self.publish(Mutation::Reorientation(redirect)).await
    }
    pub async fn take_intervention(&self, id: &str) -> Result<String, MailboxError> {
        let _guard = self.changes.lock().await;
        let request = self.request_view(id).await?;
        if request.effective_nature != RequestNature::Intervention
            || request.taken
            || request.closure.is_some()
        {
            return Err(refusal(
                "intervention_indisponible",
                "Cette intervention n’attend plus de prise en charge.",
            ));
        }
        self.event(Change::Taken {
            request_id: id.into(),
        })
        .await
    }
    pub async fn close_request(&self, closure: RequestClosure) -> Result<String, MailboxError> {
        let _guard = self.changes.lock().await;
        if !safe_id(&closure.id)
            || chrono::DateTime::parse_from_rfc3339(&closure.closed_at).is_err()
        {
            return Err(refusal(
                "cloture_invalide",
                "La clôture doit avoir un identifiant et une date valides.",
            ));
        }
        let request = self.request_view(&closure.request_id).await?;
        self.require_account(&closure.by).await?;
        if self.resolve_account(&request.request.opened_by).await?
            != self.resolve_account(&closure.by).await?
        {
            return Err(refusal(
                "pas_ouvreur",
                "Seul l’agent ouvrant peut clôturer sa demande.",
            ));
        }
        if self.find("closure", &closure.id).await? == Some(Mutation::Closure(closure.clone())) {
            return self.publish(Mutation::Closure(closure)).await;
        }
        if request.closure.is_some() {
            return Err(refusal(
                "demande_cloturee",
                "Cette demande est déjà clôturée.",
            ));
        }
        if request.effective_nature == RequestNature::Validation
            && (request.verdict.is_none() || request.decision_journey.as_deref() == Some("pending"))
        {
            return Err(refusal(
                "decision_attendue",
                "La validation attend encore une décision humaine.",
            ));
        }
        if !single_line(&closure.result) {
            return Err(refusal(
                "resultat_invalide",
                "Indique le résultat final sur une ligne non vide.",
            ));
        }
        self.publish(Mutation::Closure(closure)).await
    }
    pub async fn approvals(
        &self,
        opened_by: Option<&str>,
    ) -> Result<Vec<ApprovalView>, MailboxError> {
        let verdicts = self.rows("verdict").await?;
        let redirects = self.rows("reorientation").await?;
        let closures = self.rows("closure").await?;
        let events = self.events().await?;
        let rows = self.store.mutations(None, None).await?;
        let mut views = Vec::new();
        for mutation in self.rows("approval").await? {
            if let Mutation::Approval(request) = mutation {
                if let Some(account) = opened_by {
                    if self.resolve_account(account).await?
                        != self.resolve_account(&request.opened_by).await?
                    {
                        continue;
                    }
                }
                let verdict = verdicts.iter().find_map(|v| match v {
                    Mutation::Verdict(v) if v.request_id == request.id => Some(v.clone()),
                    _ => None,
                });
                let reorientation = redirects.iter().find_map(|v| match v {
                    Mutation::Reorientation(v) if v.request_id == request.id => Some(v.clone()),
                    _ => None,
                });
                let closure = closures
                    .iter()
                    .filter_map(|v| match v {
                        Mutation::Closure(v) if v.request_id == request.id => Some(v.clone()),
                        _ => None,
                    })
                    .min_by(|a, b| a.closed_at.cmp(&b.closed_at));
                let taken = events.iter().any(
                    |e| matches!(&e.change,Change::Taken{request_id} if request_id==&request.id),
                );
                let effective_nature = if reorientation.is_some() {
                    RequestNature::Intervention
                } else {
                    request.nature
                };
                let decision_kind = if verdict.is_some() {
                    Some("verdict")
                } else if reorientation.is_some() {
                    Some("reorientation")
                } else {
                    None
                };
                let decision_journey = decision_kind.and_then(|kind| {
                    rows.iter()
                        .find(|r| {
                            r.mutation.kind() == kind
                                && r.mutation.id() == request.id
                                && r.journey != "conflict"
                        })
                        .map(|r| r.journey.clone())
                });
                let closure_journey = closure.as_ref().and_then(|closure| {
                    rows.iter()
                        .find(|r| {
                            r.mutation.kind() == "closure"
                                && r.mutation.id() == closure.id
                                && r.journey != "conflict"
                        })
                        .map(|r| r.journey.clone())
                });
                views.push(ApprovalView {
                    request,
                    verdict,
                    reorientation,
                    closure,
                    taken,
                    effective_nature,
                    decision_journey,
                    closure_journey,
                });
            }
        }
        views.sort_by(|a, b| b.request.opened_at.cmp(&a.request.opened_at));
        Ok(views)
    }
    pub async fn agent_approvals(&self, account: &str) -> Result<Vec<ApprovalView>, MailboxError> {
        let mut views = self.approvals(Some(account)).await?;
        for view in &mut views {
            if view.decision_journey.as_deref() == Some("pending") {
                view.verdict = None;
                view.reorientation = None;
                view.effective_nature = view.request.nature;
            }
        }
        Ok(views)
    }
}
pub(crate) fn validate_request(request: &ApprovalRequest) -> Result<(), MailboxError> {
    if !safe_id(&request.id) {
        return Err(refusal(
            "demande_invalide",
            "L’identifiant de la demande est invalide.",
        ));
    }
    if [
        &request.id,
        &request.gesture,
        &request.scope,
        &request.reversible,
        &request.if_refused,
        &request.why_now,
    ]
    .iter()
    .any(|v| !single_line(v))
        || chrono::DateTime::parse_from_rfc3339(&request.opened_at).is_err()
    {
        return Err(refusal("demande_invalide","Les champs de la demande doivent être renseignés sur une ligne chacun, avec une date valide."));
    }
    Ok(())
}
fn validate_note(note: Option<&str>) -> Result<(), MailboxError> {
    if note.is_some_and(|v| !single_line(v)) {
        return Err(refusal(
            "note_invalide",
            "La note doit tenir sur une ligne non vide.",
        ));
    }
    Ok(())
}
