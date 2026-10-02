use super::MailboxError;
use crate::test_support::*;

fn position(cursor: &str) -> u64 {
    cursor.rsplit_once(':').unwrap().1.parse().unwrap()
}

#[tokio::test]
async fn the_cursor_follows_publications_and_integrations() {
    let root = Temporary::new();
    let first = root.mailbox("first").await;
    let second = root.mailbox("second").await;
    let a = account(&first, "alpha").await;
    let b = account(&first, "beta").await;
    first.send(message("m1", &a, &b)).await.unwrap();
    let (read, cursor) = first.read_after(None, 100).await.unwrap();
    assert!(read.iter().any(|(_, m)| m.id() == "m1"));
    assert!(read.windows(2).all(|pair| position(&pair[0].0) < position(&pair[1].0)));
    assert_eq!(position(&cursor), position(&read.last().unwrap().0));
    first.send(message("m2", &a, &b)).await.unwrap();
    let (next, _) = first.read_after(Some(&cursor), 100).await.unwrap();
    assert!(next.iter().any(|(_, m)| m.id() == "m2"));
    assert!(next.iter().all(|(at, m)| m.id() != "m1" && position(at) > position(&cursor)), "exactly what followed");
    // Another installation places what it integrates in its own order.
    second.receive().await.unwrap();
    let (seen, _) = second.read_after(None, 100).await.unwrap();
    let order = seen.iter().map(|(_, m)| m.id().to_owned()).collect::<Vec<_>>();
    let one = order.iter().position(|id| id == "m1").unwrap();
    let two = order.iter().position(|id| id == "m2").unwrap();
    assert!(one < two);
    let (page, after_page) = second.read_after(None, 1).await.unwrap();
    assert_eq!(page.len(), 1);
    assert_eq!(after_page, page[0].0, "a page ends on the cursor of its last record");
}

#[tokio::test]
async fn a_cursor_from_another_base_is_named() {
    let root = Temporary::new();
    let one = root.mailbox("one").await;
    let other = root.mailbox("other").await;
    let (_, cursor) = one.read_after(None, 10).await.unwrap();
    for refused in [other.read_after(Some(&cursor), 10).await, one.read_after(Some("sans-deux-points"), 10).await] {
        match refused.unwrap_err() {
            MailboxError::Refusal { reason, .. } => assert_eq!(reason, "curseur_inconnu"),
            other => panic!("expected a refusal, got {other}"),
        }
    }
}
