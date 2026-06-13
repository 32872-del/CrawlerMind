# Private Core Capability Gate

CLM uses a transparent capability gate for future private extensions.

The goal is not to break Community users or hide destructive behavior. The goal
is to keep Community features runnable while making advanced private features
explicitly require an owner-controlled token or private package.

## Principle

```text
Community feature missing license -> still works
Private feature missing license   -> clear unavailable status, degrade safely
Private feature with license      -> enabled
```

There are no hidden kill switches, silent output corruption, or sabotage paths.

## Capability Names

Community capabilities use:

```text
community.*
```

Private capabilities use:

```text
private.*
enterprise.*
pro.*
```

Current planned private capabilities:

```text
private.managed_repair_policy
private.site_profiles
private.advanced_api_replay
private.browser_profile_strategy
private.training_assets
```

## Check Status

```bash
python clm.py check --capabilities
python clm.py license check
python clm.py license check --capability private.advanced_api_replay
```

Without a license token, Community capabilities show available and private
capabilities show unavailable.

## Token Format

The local token format is:

```text
clm1.<base64url-json-payload>.<base64url-hmac-sha256-signature>
```

The verification secret is read from:

```text
CLM_LICENSE_SECRET
```

The token is read from:

```text
CLM_LICENSE_TOKEN
```

or from `clm_config.json`:

```json
{
  "license": {
    "token": "clm1....",
    "secret": "local-owner-secret"
  }
}
```

For a public deployment, do not ship the signing secret. Keep signing on the
owner side or server side.

## Future Private Package Integration

When private modules are split into a package such as `clm_private_core`, public
CLM should load them through a registry:

```text
if gate.check("private.advanced_api_replay").available:
    load private replay strategy
else:
    use Community replay strategy or explain unavailable status
```

Recommended private package shape:

```text
clm_private_core/
  managed_policy/
  repair_policy/
  profile_library/
  replay_advanced/
  browser_profile_advanced/
  training_assets/
```

## What This Protects

This protects against casual parameter/profile reuse because high-value private
features can require a signed capability token or private package. It does not
replace legal protection, private repository controls, or proper release
management.
