use super::MailboxService;
use crate::{
    domain::{journal::*, models::*, ports::*},
    exchange::DirectoryExchange,
    storage::LocalStore,
    test_support::*,
};
use serde_json::Value;
use std::{
    sync::{
        atomic::{AtomicUsize, Ordering},
        Arc,
    },
    time::Duration,
};

#[derive(Clone, Default)]
struct Counts {
    saves: Arc<AtomicUsize>,
    lists: Arc<AtomicUsize>,
    checkpoints: Arc<AtomicUsize>,
}

impl Counts {
    fn of(counter: &Arc<AtomicUsize>) -> usize {
        counter.load(Ordering::SeqCst)
    }
}

struct CountingStore(LocalStore, Counts);

impl RepositoryPort for CountingStore {
    async fn schema_version(&self) -> Result<u8, PortError> {
        self.0.schema_version().await
    }
    async fn save(&self, mutation: &Mutation, journey: &str) -> Result<bool, PortError> {
        self.1.saves.fetch_add(1, Ordering::SeqCst);
        self.0.save(mutation, journey).await
    }
    async fn mutations(
        &self,
        kind: Option<&str>,
        journey: Option<&str>,
    ) -> Result<Vec<StoredMutation>, PortError> {
        self.0.mutations(kind, journey).await
    }
    async fn set_journey(&self, kind: &str, id: &str, journey: &str) -> Result<(), PortError> {
        self.0.set_journey(kind, id, journey).await
    }
    async fn setting(&self, key: &str) -> Result<Option<Value>, PortError> {
        self.0.setting(key).await
    }
    async fn set_setting(&self, key: &str, value: Value) -> Result<(), PortError> {
        self.0.set_setting(key, value).await
    }
    async fn save_blob(&self, reference: &Attachment, bytes: Vec<u8>) -> Result<(), PortError> {
        self.0.save_blob(reference, bytes).await
    }
    async fn blob(&self, fingerprint: &str) -> Result<Option<Vec<u8>>, PortError> {
        self.0.blob(fingerprint).await
    }
}

/// A box that counts its readings and checkpoints, and can take its time to answer a listing.
struct CountingExchange(DirectoryExchange, Counts, Duration);

impl ExchangePort for CountingExchange {
    fn deposit(&self, item: ExchangeItem<'_>) -> Result<String, PortError> {
        if matches!(item, ExchangeItem::Checkpoint(_)) {
            self.1.checkpoints.fetch_add(1, Ordering::SeqCst);
        }
        self.0.deposit(item)
    }
    fn list(&self, since: Option<&str>, attachments: &[Attachment]) -> Result<ExchangeBatch, PortError> {
        self.1.lists.fetch_add(1, Ordering::SeqCst);
        std::thread::sleep(self.2);
        self.0.list(since, attachments)
    }
    fn listen(&self) -> Result<tokio::sync::watch::Receiver<u64>, PortError> {
        self.0.listen()
    }
}

async fn counting(
    root: &Temporary,
    name: &str,
    delay: Duration,
) -> (MailboxService<CountingStore, CountingExchange>, Counts) {
    let shared = root.0.join("shared");
    std::fs::create_dir_all(&shared).unwrap();
    let counts = Counts::default();
    let store = LocalStore::open(root.0.join(name)).await.unwrap();
    let mailbox = MailboxService::with_installation(
        CountingStore(store, counts.clone()),
        CountingExchange(DirectoryExchange::new(shared), counts.clone(), delay),
        name.into(),
        format!("machine-{name}"),
    );
    (mailbox, counts)
}

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn receives_called_together_share_one_reading_of_the_box() {
    let root = Temporary::new();
    let (mailbox, counts) = counting(&root, "one", Duration::from_millis(300)).await;
    let mailbox = Arc::new(mailbox);
    let first = tokio::spawn({
        let mailbox = mailbox.clone();
        async move { mailbox.receive().await.unwrap() }
    });
    tokio::time::sleep(Duration::from_millis(100)).await;
    let others = (0..3)
        .map(|_| {
            let mailbox = mailbox.clone();
            tokio::spawn(async move { mailbox.receive().await.unwrap() })
        })
        .collect::<Vec<_>>();
    first.await.unwrap();
    for other in others {
        other.await.unwrap();
    }
    // The relève already running, then a single one for the three calls that arrived meanwhile.
    assert_eq!(Counts::of(&counts.lists), 2);
}

#[tokio::test]
async fn a_receive_skips_what_it_already_integrated() {
    let root = Temporary::new();
    let first = root.mailbox("first").await;
    let alpha = account(&first, "alpha").await;
    let beta = account(&first, "beta").await;
    first.send(message("m1", &alpha, &beta)).await.unwrap();
    let (second, counts) = counting(&root, "second", Duration::ZERO).await;
    second.receive().await.unwrap();
    let saves = Counts::of(&counts.saves);
    assert!(saves > 0);
    second.receive().await.unwrap();
    assert_eq!(Counts::of(&counts.saves), saves, "nothing new: the store is left alone");
    first.send(message("m2", &alpha, &beta)).await.unwrap();
    let integrated = second.receive().await.unwrap();
    assert!(integrated >= 1);
    assert_eq!(Counts::of(&counts.saves), saves + integrated, "only what is new is saved");
}

#[tokio::test]
async fn an_idle_receive_writes_no_checkpoint_until_something_changes() {
    let root = Temporary::new();
    let first = root.mailbox("first").await;
    let alpha = account(&first, "alpha").await;
    let beta = account(&first, "beta").await;
    let (second, counts) = counting(&root, "second", Duration::ZERO).await;
    second.receive().await.unwrap();
    assert_eq!(Counts::of(&counts.checkpoints), 1);
    second.receive().await.unwrap();
    assert_eq!(Counts::of(&counts.checkpoints), 1);
    first.send(message("m", &alpha, &beta)).await.unwrap();
    second.receive().await.unwrap();
    assert_eq!(Counts::of(&counts.checkpoints), 2);
}

#[tokio::test]
async fn resuming_from_the_same_place_publishes_no_account() {
    let root = Temporary::new();
    let mailbox = root.mailbox("one").await;
    let enrolled = mailbox
        .enroll("codex", "session-a", "Alice", "développeur", None)
        .await
        .unwrap();
    let address = enrolled["identity"]["account"].as_str().unwrap().to_owned();
    let key = enrolled["recovery_key"].as_str().unwrap().to_owned();
    let published = |rows: Vec<Mutation>| {
        rows.into_iter()
            .filter(|row| {
                matches!(row, Mutation::Event(Event { change: Change::Account { account }, .. }) if account.address == address)
            })
            .count()
    };
    let before = published(mailbox.rows("event").await.unwrap());
    mailbox.recognize("codex", "session-b", &address, &key).await.unwrap();
    mailbox.recognize("codex", "session-c", &address, &key).await.unwrap();
    assert_eq!(published(mailbox.rows("event").await.unwrap()), before);
    mailbox.recognize("claude", "session-d", &address, &key).await.unwrap();
    assert_eq!(published(mailbox.rows("event").await.unwrap()), before + 1);
}
