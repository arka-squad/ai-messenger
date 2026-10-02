//! The integration cursor: what became visible on this base, in the order it did.
use super::*;

const ORIGIN: &str = "cursor_origin";

impl<R: RepositoryPort, E: ExchangePort> MailboxService<R, E> {
    /// Names this base. A cursor from another box or from a rebuilt base is refused, never misread.
    async fn cursor_origin(&self) -> Result<String, MailboxError> {
        if let Some(origin) = self.setting(ORIGIN).await?.and_then(|v| v.as_str().map(str::to_owned)) {
            return Ok(origin);
        }
        let origin = new_id();
        self.set_setting(ORIGIN, json!(origin)).await?;
        Ok(origin)
    }

    /// What became visible after `cursor`, oldest first, each with its own cursor, and the cursor
    /// that follows the last one read.
    #[allow(dead_code)] // Read by the observer access (lots M2 and M3).
    pub(crate) async fn read_after(
        &self,
        cursor: Option<&str>,
        limit: usize,
    ) -> Result<(Vec<(String, Mutation)>, String), MailboxError> {
        let origin = self.cursor_origin().await?;
        let after = match cursor {
            None => 0,
            Some(cursor) => cursor
                .rsplit_once(':')
                .filter(|(from, _)| *from == origin)
                .and_then(|(_, position)| position.parse::<u64>().ok())
                .ok_or_else(|| {
                    refusal(
                        "curseur_inconnu",
                        "Ce curseur ne vient pas de cette boîte ou de cette base : relis depuis le début.",
                    )
                })?,
        };
        let rows = self.store.after(after, limit).await?;
        let next = rows.last().map_or(after, |(position, _)| *position);
        let read = rows
            .into_iter()
            .filter(|(_, row)| row.journey != "conflict")
            .map(|(position, row)| (format!("{origin}:{position}"), row.mutation))
            .collect();
        Ok((read, format!("{origin}:{next}")))
    }
}
