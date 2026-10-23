# Secrets management

The launcher reads credentials through `secret-tool` and the Linux session's Secret Service. It does not install a provider or manage credentials. GNOME Keyring is the initial Ubuntu target; another provider exposing the same interface may work, but full compatibility is not guaranteed.

## Diagnose prerequisites

```bash
mcp-launcher secrets status
mcp-launcher secrets --help
```

Status checks the OS, `secret-tool`, session D-Bus, the running Secret Service provider, and collection lock metadata. It does not retrieve credentials, create test entries, unlock collections, or start/install a provider. Probes have timeouts and inspect at most 16 collections. If the metadata tool `busctl` is unavailable, the result is unknown rather than ready.

Exit status 0 means the checked prerequisites were observed ready; 1 means missing, locked, unsupported, or unknown. This does not verify that a specific profile's credentials exist. If any collection is locked, status conservatively reports attention required even if another collection is unlocked.

On Debian/Ubuntu, missing `secret-tool` produces the recommendation `sudo apt install libsecret-tools`. That installs a client, not a configured, unlocked keyring provider. Configure the provider through your desktop tools. For GUI-only failures, see [Codex session forwarding](configuration/Codex.md).

## Store or replace a credential

For this YAML reference:

```yaml
secrets:
  OUTLINE_API_KEY:
    service: outline
    profile: personal
    key: api
```

Run:

```bash
secret-tool store --label="Outline personal API" \
  service outline profile personal key api
```

Press Enter, then enter the credential at the hidden prompt.

- `--label`: a human-readable description.
- `service outline`: matches YAML `service: outline`.
- `profile personal`: matches YAML `profile: personal`.
- `key api`: matches YAML `key: api`. The word `api` is a lookup attribute, not your credential.

Reuse the same attributes to store/replace an entry. Change the attribute values to match the profile you want to use.

### More examples

Choose the example matching your YAML reference; these commands prompt for the value rather than accepting a secret argument.

```bash
# Outline: personal profile, API credential
secret-tool store --label="Outline personal API" \
  service outline profile personal key api

# OpenProject: manufacturing-readonly profile, API credential
secret-tool store --label="OpenProject manufacturing API" \
  service openproject profile manufacturing-readonly key api

# OpenProject: personal profile, private URL (as in examples/config.yaml)
secret-tool store --label="OpenProject personal URL" \
  service openproject profile personal key url
```

The environment variable name `OUTLINE_API_KEY` belongs to the launch configuration. It is not an argument to `secret-tool store`. The launcher retrieves the matching entry at launch and passes it to the server as that environment variable. Profiles do not enforce permissions: use credentials with the required scope.

Do not place the credential in command arguments. To check a known entry without printing its value, use:

```bash
secret-tool lookup service outline profile personal key api >/dev/null
```

Unlike `secrets status`, this lookup actually retrieves the credential and can involve the provider's unlock behavior. See [configuration and usage](usage.md) for complete examples.

## See which secrets exist

There is no `mcp-launcher secrets list` command today.

To see the secret **environment variable names referenced by a server's configuration**:

```bash
mcp-launcher list outline
```

This reads YAML only. It does not list actual keyring entries or confirm that those credentials exist. For the lookup attributes themselves, open the configuration:

```bash
nano "$(mcp-launcher path)"
```

To browse **stored keyring entries**, use your provider's desktop manager. On Ubuntu/GNOME, open **Passwords and Keys** (Seahorse), select your keyring, and look for the label supplied to `secret-tool store`. Its presence is desktop-dependent; the launcher does not install it. Other providers have their own interfaces.

For one known reference, use the redirected `secret-tool lookup` example above. Avoid sharing unredacted keyring command output: some tools display credential values as well as metadata.
