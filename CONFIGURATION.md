# Configuration

The backend is configured with `CP_*` environment variables, or with a `.env` file whose path is in `CP_CONFIG_PATH`. Invalid or missing values stop startup.

The options below are generated from the settings classes in `competitor_pulse/configuration.py`. Do not edit them by hand; after changing a setting run:

```bash
scripts/autogenerate-settings-docs.sh
```

<!-- options-start -->
## `CP_BIND_ADDRESS`

*Optional*, default value: `127.0.0.1`

The interface to listen on

## `CP_PORT`

*Optional*, default value: `8080`

The port to listen on

## `CP_DEBUG`

*Optional*, default value: `False`

Enable debug mode (also override the log level)

## `CP_ENABLE_HOT_RELOAD`

*Optional*, default value: `False`

Enable hot-reloading during development

## `CP_LOG_DIRECTORY`

*Optional*, default value: `None`

The directory to write log files to (it will be created if it does not exist)

## `CP_LOG_LEVEL`

*Optional*, default value: `INFO`

The log level to use

### Possible values

`TRACE`, `DEBUG`, `INFO`, `SUCCESS`, `WARNING`, `ERROR`, `CRITICAL`

## `CP_WORKERS`

*Optional*, default value: `1`

The number of worker processes to spawn

## `CP_PRETTY_PRINT_LOGS`

*Optional*, default value: `True`

Enable pretty-printing of JSON logs

## `CP_SSL_CERTFILE`

*Optional*, default value: `None`

The path to the SSL certificate file

## `CP_SSL_KEYFILE`

*Optional*, default value: `None`

The path to the SSL key file

## `CP_DATABASE_URL`

**Required**

The connection string: postgresql://user:password@host/db

## `CP_DATABASE_POOL_MIN_SIZE`

*Optional*, default value: `2`

Connections the pool keeps open while idle

## `CP_DATABASE_POOL_MAX_SIZE`

*Optional*, default value: `10`

Most connections the pool opens
<!-- options-end -->
