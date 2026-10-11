# Database layer

`create_demo_database()` creates the MVP e-commerce schema and deterministic rows. Call `seed_demo_data(connection, reset=True)` to rebuild an existing database. The returned connection is writable for setup; pass its file path to the read-only executor after seeding.
