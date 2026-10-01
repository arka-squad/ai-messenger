use crate::mailbox::{refusal, MailboxError, MAX_WAIT};
use serde_json::{json, Value};

fn schema(name: &str, description: &str, properties: Value, required: &[&str]) -> Value {
    json!({"name":name,"description":description,"inputSchema":{"type":"object","properties":properties,"required":required,"additionalProperties":false}})
}
fn field(kind: &str, description: &str) -> Value {
    json!({"type":kind,"description":description})
}
fn object(description: &str, properties: Value, required: &[&str]) -> Value {
    json!({"type":"object","description":description,"properties":properties,"required":required})
}
pub(super) fn tools() -> Value {
    let text = json!({"type":"string"});
    let dossier = field("string", "Chemin absolu de ton dossier de travail : une nouvelle session y retrouve ton compte.");
    let delivery = field("string", "Identifiant de remise donné par ton canal Messenger (Claude), ou identifiant de ta session Codex : il te réveille à l’arrivée du courrier.");
    let addresses = |description: &str| json!({"type":"array","items":{"type":"string"},"description":description});
    let message = |required: &[&str]| object("Le message ; from, la date et l’origine sont attestés par Messenger.", json!({
        "id":field("string","Identifiant facultatif ; le même identifiant rend l’envoi idempotent."),
        "to":addresses("Destinataires : adresse complète (nom@projet), nom court d’un compte actif ou alias de ton carnet."),
        "copies":addresses("Copies : elles voient le message sans le marquer ni y répondre."),
        "subject":field("string","Objet, sur une ligne."),
        "body":{"type":"array","items":{"type":"string"},"maxItems":2,"description":"Corps : deux lignes au plus ; les détails vont en pièce jointe."}}), required);
    let attachment = json!({"type":"object","description":"Pièce jointe : un fichier lisible par l’application (path absolu), ou un nom et ses octets.","properties":{"name":text,"path":field("string","Chemin absolu du fichier."),"bytes":{"type":"array","items":{"type":"integer","minimum":0,"maximum":255}}},"anyOf":[{"required":["name","bytes"]},{"required":["path"]}],"additionalProperties":false});
    let contact = object("Un alias de ton carnet.", json!({"alias":field("string","Nom court, distinct de toute adresse de compte."),"addresses":addresses("Adresses réelles des comptes visés."),"note":field("string","Note facultative.")}), &["alias","addresses"]);
    let request = object("La demande, un champ sur une ligne chacun.", json!({
        "id":field("string","Identifiant facultatif."),
        "gesture":field("string","Le geste précis attendu."),
        "scope":field("string","Ce qu’il touche."),
        "reversible":field("string","Comment revenir en arrière."),
        "if_refused":field("string","Ce que tu feras sans accord."),
        "why_now":field("string","Pourquoi maintenant.")}), &["gesture","scope","reversible","if_refused","why_now"]);
    let session = field("string", "Session de retour de la décision, si elle diffère de la tienne.");
    json!([
        schema("qui_suis_je","Retourne le compte de cette session, avec son nom et son rôle. Avec dossier, une nouvelle session retrouve le compte enrôlé ou repris dans ce dossier exact, sauf si plusieurs agents de ton outil y travaillent (dossier_partage) ou si c’est ton dossier personnel ; sans compte, la réponse liste les comptes de ce poste pour ton outil.",json!({"dossier":dossier,"delivery_session":delivery}),&[]),
        schema("m_enroler","Crée ton compte, ou te rend celui que cette installation t’a déjà donné pour la même tâche ; une session liée à un autre compte passe sur celui-ci. Le nom est déduit de ton outil, de ta tâche et du système de cet ordinateur (ex. CL_Agent-MessengerAI_WIN). La clé de reprise n’est jamais publiée.",json!({"tache":field("string","Titre court et durable de ta tâche, ex. MessengerAI ; il entre dans ton nom de compte."),"role":field("string","Ton rôle exact, sur une ligne."),"project":field("string","Projet de ton dépôt ; sans projet, le compte est commun."),"dossier":dossier,"delivery_session":delivery}),&["tache","role"]),
        schema("me_reconnaitre","Reprend ton compte avec ta clé de reprise ; une session liée à un autre compte passe sur celui-ci.",json!({"account":text,"recovery_key":text,"dossier":dossier,"delivery_session":delivery}),&["account","recovery_key"]),
        schema("relever","Relève les messages qui te sont adressés et non traités, sans modifier leurs statuts, ainsi que chaque copie à la première relève qui suit son arrivée ; une copie déjà rendue reste lisible avec lire et ou_en_est.",json!({"account":text}),&[]),
        schema("lire","Lit un message visible par ton compte ; la lecture seule ne marque rien.",json!({"account":text,"id":text}),&["id"]),
        schema("envoyer","Dépose un message immuable. Le résultat donne les destinataires résolus et distingue attente et publication prouvée.",json!({"message":message(&["to","subject"]),"attachment":attachment}),&["message"]),
        schema("repondre","Publie une réponse liée au message d’origine ; sans to, elle va à son expéditeur.",json!({"reply_to":field("string","Identifiant du message d’origine."),"message":message(&["subject"]),"attachment":attachment}),&["reply_to","message"]),
        schema("marquer","Avance ton statut de destinataire : lu une fois lu, traité une fois traité. Les copies ne marquent rien.",json!({"marking":object("Le marquage.",json!({"id":field("string","Identifiant facultatif."),"message_id":text,"status":{"type":"string","enum":["lu","traité"]}}),&["message_id","status"])}),&["marking"]),
        schema("agents","Liste les comptes de la boîte et leurs adresses réelles ; disponible avant l’enrôlement.",json!({}),&[]),
        schema("contacts","Retourne ton carnet privé. ajouter ou retirer modifient un alias ; contacts remplace le carnet entier. Un alias s’utilise comme destinataire.",json!({"contacts":{"type":"array","items":contact},"ajouter":contact,"retirer":field("string","Alias à retirer.")}),&[]),
        schema("demander_validation","Demande à l’humain de valider ou refuser un geste décrit précisément.",json!({"request":request,"session":session}),&["request"]),
        schema("demander_intervention","Demande une intervention de l’humain dans ta session ; aucune autorisation n’est accordée.",json!({"request":request,"session":session}),&["request"]),
        schema("ou_en_est","Retourne le trajet, l’atteinte et le statut du courrier, ainsi que les décisions et résultats de tes demandes.",json!({"account":text}),&[]),
        schema("cloturer_ma_demande","Clôture uniquement une demande ouverte par ton compte, avec son résultat final.",json!({"closure":object("La clôture.",json!({"id":field("string","Identifiant facultatif."),"request_id":text,"result":field("string","Résultat final, sur une ligne.")}),&["request_id","result"])}),&["closure"]),
        schema("attendre","Attend le courrier arrivé après l’appel, ou encore nouveau et jamais remis à cette session, sans marquer lu ; rend la main dès son arrivée.",json!({"secondes":{"type":"integer","minimum":0,"maximum":MAX_WAIT,"description":"Délai maximal en secondes : 50 par défaut, 1800 au plus. Reste sous le délai d’outil de ton hôte (Codex : 60 s par défaut), sinon l’hôte abandonne l’appel avant sa réponse."}}),&[]),
        schema("modifier_mon_role","Remplace le rôle de ton propre compte.",json!({"role":field("string","Nouveau rôle, sur une ligne.")}),&["role"])
    ])
}

/// Shapes the first mailbox accepted: a body as text, a single recipient as text, a contact without note.
pub(super) fn normalize(name: &str, args: &mut Value) {
    if let Some(message) = args.get_mut("message").and_then(Value::as_object_mut) {
        if let Some(body) = message.get("body").and_then(Value::as_str) {
            let lines = body.lines().filter(|l| !l.trim().is_empty()).map(str::to_owned).collect::<Vec<_>>();
            message.insert("body".into(), json!(lines));
        }
        for key in ["to", "copies"] {
            if let Some(single) = message.get(key).and_then(Value::as_str).map(str::to_owned) {
                message.insert(key.into(), json!([single]));
            }
        }
    }
    if name == "contacts" {
        let fill = |contact: &mut Value| {
            if let Some(contact) = contact.as_object_mut() {
                contact.entry("note").or_insert_with(|| json!(""));
            }
        };
        if let Some(book) = args.get_mut("contacts").and_then(Value::as_array_mut) {
            book.iter_mut().for_each(fill);
        }
        if let Some(added) = args.get_mut("ajouter") {
            fill(added);
        }
    }
}

pub(super) fn validate(name: &str, args: &Value) -> Result<(), MailboxError> {
    let tools = tools();
    let tool = tools
        .as_array()
        .and_then(|t| t.iter().find(|t| t["name"] == name))
        .ok_or_else(|| refusal("outil_inconnu", "Cet outil Messenger n’existe pas."))?;
    check(&tool["inputSchema"], args, "")
}

fn check(schema: &Value, value: &Value, path: &str) -> Result<(), MailboxError> {
    let shown = if path.is_empty() { "arguments" } else { path };
    let invalid = |text: String| refusal("argument_invalide", &text);
    if let Some(kind) = schema["type"].as_str() {
        let (fits, expected) = match kind {
            "object" => (value.is_object(), "un objet"),
            "array" => (value.is_array(), "une liste"),
            "string" => (value.is_string(), "un texte"),
            "integer" => (value.is_i64() || value.is_u64(), "un entier"),
            "boolean" => (value.is_boolean(), "un booléen"),
            _ => (true, ""),
        };
        if !fits {
            return Err(invalid(format!("{shown} doit être {expected}.")));
        }
    }
    if let Some(options) = schema["enum"].as_array() {
        if !options.contains(value) {
            let names = options.iter().filter_map(Value::as_str).collect::<Vec<_>>().join(" ou ");
            return Err(invalid(format!("{shown} doit valoir {names}.")));
        }
    }
    if let Some(number) = value.as_i64() {
        let (min, max) = (schema["minimum"].as_i64(), schema["maximum"].as_i64());
        if min.is_some_and(|m| number < m) || max.is_some_and(|m| number > m) {
            return Err(invalid(format!("{shown} doit être compris entre {} et {}.", min.unwrap_or(0), max.unwrap_or(i64::MAX))));
        }
    }
    if let Some(items) = value.as_array() {
        if let Some(max) = schema["maxItems"].as_u64().filter(|m| items.len() as u64 > *m) {
            return Err(invalid(format!("{shown} accepte au plus {max} éléments.")));
        }
        for (index, item) in items.iter().enumerate() {
            check(&schema["items"], item, &format!("{shown}[{index}]"))?;
        }
    }
    if let Some(object) = value.as_object() {
        let join = |key: &str| if path.is_empty() { key.to_owned() } else { format!("{path}.{key}") };
        for key in schema["required"].as_array().into_iter().flatten().filter_map(Value::as_str) {
            if object.get(key).is_none_or(Value::is_null) {
                return Err(refusal("argument_manquant", &format!("L’argument {} manque.", join(key))));
            }
        }
        for (key, inner) in schema["properties"].as_object().into_iter().flatten() {
            if let Some(v) = object.get(key).filter(|v| !v.is_null()) {
                check(inner, v, &join(key))?;
            }
        }
    }
    if let Some(branches) = schema["anyOf"].as_array() {
        if !branches.iter().any(|b| check(b, value, path).is_ok()) {
            let shapes = branches.iter().map(|b| {
                b["required"].as_array().into_iter().flatten().filter_map(Value::as_str).collect::<Vec<_>>().join(" et ")
            });
            return Err(invalid(format!("{shown} : indique {}.", shapes.collect::<Vec<_>>().join(", ou "))));
        }
    }
    Ok(())
}
