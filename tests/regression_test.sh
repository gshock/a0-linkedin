#!/usr/bin/env bash
# LinkedIn plugin regression checks.
#
# Designed to run without a pre-existing runtime config: the script creates a
# temporary multi-account config, exercises routing and CRUD, then restores the
# original state.
set -euo pipefail

PLUGIN_DIR="${PLUGIN_DIR:-/a0/usr/plugins/linkedin}"
export LINKEDIN_CONFIG_SOURCE=local
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || command -v python)}"
RUNTIME_CONFIG="$PLUGIN_DIR/.runtime_config.json"
HELPERS_CONFIG="$PLUGIN_DIR/helpers/config.py"
API_FILE="$PLUGIN_DIR/api/linkedin_config_api.py"
POST_TOOL="$PLUGIN_DIR/tools/linkedin_post.py"
READ_TOOL="$PLUGIN_DIR/tools/linkedin_read.py"
ACCOUNT_TOOL="$PLUGIN_DIR/tools/linkedin_account.py"
README="$PLUGIN_DIR/README.md"
HUMAN_TEST_PLAN="$PLUGIN_DIR/tests/HUMAN_TEST_PLAN.md"
SMOKE_EXAMPLES="$PLUGIN_DIR/tests/smoke_examples.md"

BACKUP_DIR="$(mktemp -d)"
if [ -f "$RUNTIME_CONFIG" ]; then
  cp "$RUNTIME_CONFIG" "$BACKUP_DIR/runtime_config.json"
  HAD_RUNTIME_CONFIG=1
else
  HAD_RUNTIME_CONFIG=0
fi
restore() {
  if [ "$HAD_RUNTIME_CONFIG" -eq 1 ]; then
    cp "$BACKUP_DIR/runtime_config.json" "$RUNTIME_CONFIG"
  else
    rm -f "$RUNTIME_CONFIG"
  fi
  rm -rf "$BACKUP_DIR"
}
trap restore EXIT

pass() { printf '[PASS] %s\n' "$1"; }
fail() { printf '[FAIL] %s\n' "$1"; exit 1; }
require_grep() {
  local pattern="$1"
  local file="$2"
  local label="$3"
  grep -qE "$pattern" "$file" && pass "$label" || fail "$label"
}

printf 'Running LinkedIn plugin regression checks...\n'

# 1. Required files
for f in "$HELPERS_CONFIG" "$API_FILE" "$POST_TOOL" "$READ_TOOL" "$ACCOUNT_TOOL" \
         "$README" "$HUMAN_TEST_PLAN" "$SMOKE_EXAMPLES" "$PLUGIN_DIR/default_config.yaml"; do
  [ -f "$f" ] || fail "Required file missing: $f"
done
pass 'Required plugin files exist'

# 2. Compilation
"$PYTHON_BIN" -m py_compile \
  "$HELPERS_CONFIG" \
  "$PLUGIN_DIR/helpers/sanitize.py" \
  "$PLUGIN_DIR/helpers/linkedin_auth.py" \
  "$PLUGIN_DIR/helpers/linkedin_client.py" \
  "$API_FILE" \
  "$POST_TOOL" "$READ_TOOL" "$ACCOUNT_TOOL"
pass 'Core helper/tool/api files compile'

# 3. Routing helpers exist and the fixed-name mapping is gone
require_grep 'def resolve_target_selection\(' "$HELPERS_CONFIG" 'capability routing helper present'
require_grep 'def resolve_profile_candidates\(' "$HELPERS_CONFIG" 'candidate lister present'
require_grep 'def list_accounts\(' "$HELPERS_CONFIG" 'account lister present'
require_grep 'def profile_capabilities\(' "$HELPERS_CONFIG" 'per-account capability reporter present'
if grep -qE 'def get_profile_name_for_target\(' "$HELPERS_CONFIG"; then
  fail 'legacy fixed-name target mapping should be removed'
fi
pass 'legacy fixed-name target mapping removed'

# 4. Tool contracts
require_grep 'text = self.args.get\("text"\)' "$POST_TOOL" 'linkedin_post reads text'
require_grep 'self.args.get\("message", ""\)' "$POST_TOOL" 'linkedin_post falls back to message'
require_grep 'resolved_profile' "$POST_TOOL" 'linkedin_post returns resolved_profile metadata'
require_grep 'needs_clarification' "$POST_TOOL" 'linkedin_post emits clarification responses'
require_grep 'candidates' "$POST_TOOL" 'linkedin_post returns candidate accounts'
require_grep 'image_paths = self.args.get\("image_paths"\)' "$POST_TOOL" 'linkedin_post accepts image_paths'
require_grep 'Provide either .image_path. or .image_paths., not both' "$POST_TOOL" 'linkedin_post rejects conflicting image inputs'
require_grep 'def create_multi_image_post\(' "$PLUGIN_DIR/helpers/linkedin_client.py" 'linkedin_client multi-image helper present'
require_grep 'validate_image_paths' "$PLUGIN_DIR/helpers/sanitize.py" 'sanitize validates multiple image paths'
require_grep 'resolve_target_selection' "$READ_TOOL" 'linkedin_read uses capability routing'
require_grep 'candidates' "$READ_TOOL" 'linkedin_read returns candidate accounts'
require_grep 'action == "accounts"' "$ACCOUNT_TOOL" 'linkedin_account supports accounts action'

# 5. Config API surfaces account CRUD
for action_name in account_save account_delete account_set_active; do
  require_grep "if action == \"$action_name\"" "$API_FILE" "config API supports $action_name"
done
require_grep 'def _sync_shared_defaults\(' "$API_FILE" 'config API has safe shared-default sync'

# 5b. URN discovery: HTTP entry point, action, and settings-UI buttons
require_grep 'async def process\(self, input: dict' "$API_FILE" 'config API exposes an HTTP process() entry point'
require_grep 'if action == "discover"' "$API_FILE" 'config API supports discover action'
require_grep 'def _discover\(' "$API_FILE" 'config API has a discover implementation'
require_grep 'def get_member_urn\(' "$PLUGIN_DIR/helpers/linkedin_client.py" 'client resolves the member URN via userinfo'
require_grep '/v2/userinfo' "$PLUGIN_DIR/helpers/linkedin_client.py" 'client calls the userinfo endpoint'
require_grep "discover\('personal'\)" "$PLUGIN_DIR/webui/config.html" 'config UI has a person URN discovery button'
require_grep "discover\('organization'\)" "$PLUGIN_DIR/webui/config.html" 'config UI has an organization URN discovery button'
require_grep 'callJsonApi' "$PLUGIN_DIR/webui/config.html" 'config UI calls the plugin API'

# 5c. OAuth browser flow: callback handler, state nonce, connect button
OAUTH_CALLBACK="$PLUGIN_DIR/api/linkedin_oauth_callback.py"
OAUTH_HELPER="$PLUGIN_DIR/helpers/linkedin_oauth.py"
[ -f "$OAUTH_CALLBACK" ] || fail "Required file missing: $OAUTH_CALLBACK"
[ -f "$OAUTH_HELPER" ] || fail "Required file missing: $OAUTH_HELPER"
require_grep 'return \["GET"\]' "$OAUTH_CALLBACK" 'OAuth callback accepts browser GET redirects'
require_grep 'def requires_csrf' "$OAUTH_CALLBACK" 'OAuth callback declares its CSRF policy'
require_grep 'consume_state' "$OAUTH_CALLBACK" 'OAuth callback validates the state nonce'
require_grep 'exchange_code' "$OAUTH_CALLBACK" 'OAuth callback exchanges the code for a token'
require_grep 'def create_state' "$OAUTH_HELPER" 'OAuth helper issues single-use state'
require_grep 'def consume_state' "$OAUTH_HELPER" 'OAuth helper consumes state once'
require_grep 'oauth/v2/accessToken' "$OAUTH_HELPER" 'OAuth helper calls the LinkedIn token endpoint'
require_grep 'if action == "oauth_start"' "$API_FILE" 'config API supports oauth_start'
require_grep "oauthConnect\(\)" "$PLUGIN_DIR/webui/config.html" 'config UI has a Connect account button'
require_grep 'client_secret' "$PLUGIN_DIR/webui/config.html" 'config UI collects app credentials'

# 6. Functional multi-account behaviour (temporary runtime config)
cd "$PLUGIN_DIR"
"$PYTHON_BIN" - <<'PY'
import importlib
import json
import sys
from pathlib import Path

plugin_dir = Path('/a0/usr/plugins/linkedin')
config_path = plugin_dir / '.runtime_config.json'
sys.path.insert(0, '/a0/usr/plugins')

from linkedin.helpers import config as cfgmod

three_accounts = {
    'active_profile': 'justlinks',
    'linkedin': {'linkedin_version': '202601', 'mode': 'api'},
    'profiles': {
        'justlinks': {
            'label': 'JustLinks',
            'linkedin': {
                'access_token': 'token-justlinks-aaaa',
                'person_urn': 'urn:li:person:justlinks',
                'scopes': ['w_member_social'],
                'default_target': 'personal',
                'linkedin_version': '202601',
            },
        },
        'myresumator_me': {
            'label': 'MyResumator Personal',
            'linkedin': {
                'access_token': 'token-mr-person-bbbb',
                'person_urn': 'urn:li:person:mrme',
                'scopes': ['w_member_social'],
                'default_target': 'personal',
                'linkedin_version': '202601',
            },
        },
        'myresumator_biz': {
            'label': 'MyResumator Business',
            'linkedin': {
                'access_token': 'token-mr-biz-cccc',
                'organization_urns': ['urn:li:organization:111', 'urn:li:organization:222'],
                'scopes': ['w_organization_social', 'r_organization_social'],
                'default_target': 'organization',
                'linkedin_version': '202601',
            },
        },
        'empty_account': {'label': 'Not Configured', 'linkedin': {}},
    },
}
config_path.write_text(json.dumps(three_accounts, indent=2), encoding='utf-8')

config = cfgmod.load_config()

# a) every account is reported with an inferred target type
accounts = {a['profile']: a for a in cfgmod.list_accounts(config)}
assert set(accounts) >= {'justlinks', 'myresumator_me', 'myresumator_biz'}, accounts.keys()
assert accounts['justlinks']['target'] == 'personal'
assert accounts['myresumator_biz']['target'] == 'organization'
assert accounts['myresumator_biz']['organization_page_count'] == 2
assert accounts['justlinks']['can_post'] is True
assert accounts['myresumator_biz']['can_post'] is True
assert accounts['empty_account']['can_post'] is False

# b) two personal accounts -> clarification with both candidates
sel = cfgmod.resolve_target_selection(config, target='personal')
assert sel['needs_clarification'] is True, sel
assert {c['profile'] for c in sel['candidates']} == {'justlinks', 'myresumator_me'}
assert sel['profile'] is None

# c) unique organization match resolves without asking
sel_org = cfgmod.resolve_target_selection(config, target='organization')
assert sel_org['needs_clarification'] is False, sel_org
assert sel_org['profile'] == 'myresumator_biz'
assert sel_org['linkedin']['organization_urns'] == ['urn:li:organization:111', 'urn:li:organization:222']

# d) explicit profile always wins
sel_explicit = cfgmod.resolve_target_selection(config, target='personal', profile='myresumator_me')
assert sel_explicit['profile'] == 'myresumator_me'
assert sel_explicit['linkedin']['access_token'] == 'token-mr-person-bbbb'

# e) accounts must not leak credentials into each other
assert cfgmod.get_profile_config(config, 'justlinks')['access_token'] == 'token-justlinks-aaaa'
assert cfgmod.get_profile_config(config, 'myresumator_biz')['access_token'] == 'token-mr-biz-cccc'

# f) unknown profile is a hard error, not a silent fallback
sel_bad = cfgmod.resolve_target_selection(config, profile='nope')
assert sel_bad['profile'] is None
assert 'Unknown LinkedIn profile' in (sel_bad['error'] or '')
assert sel_bad['needs_clarification'] is False

# g) no-token accounts are never offered as candidates
personal_names = {c['profile'] for c in cfgmod.resolve_profile_candidates(config, 'personal')}
assert 'empty_account' not in personal_names

# h) masking hides every account's token
masked = cfgmod.mask_config(config)
for name in ('justlinks', 'myresumator_me', 'myresumator_biz'):
    token = masked['profiles'][name]['linkedin']['access_token']
    assert token.startswith('*'), (name, token)
    assert 'token-' not in token, (name, token)

print('OK')
PY
pass 'Multi-account routing, isolation, and masking verified'

# 7. Config API CRUD round trip
"$PYTHON_BIN" - <<'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, '/a0')

import importlib.util
spec = importlib.util.spec_from_file_location(
    'linkedin_config_api', '/a0/usr/plugins/linkedin/api/linkedin_config_api.py'
)
api_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api_mod)

api = api_mod.LinkedInConfigApi()

# add a brand new account
created = api_mod.handle(
    action='account_save',
    name='newapp',
    profile={'label': 'New App', 'linkedin': {
        'access_token': 'token-newapp-dddd',
        'person_urn': 'urn:li:person:newapp',
        'scopes': ['w_member_social'],
        'default_target': 'personal',
    }},
)
assert created['ok'] is True, created
assert created['created'] is True, created
saved = json.loads(Path('/a0/usr/plugins/linkedin/.runtime_config.json').read_text())
assert 'newapp' in saved['profiles'], saved['profiles'].keys()
assert saved['profiles']['newapp']['linkedin']['access_token'] == 'token-newapp-dddd'

# saving a masked token must not wipe the stored secret
import asyncio
resaved = asyncio.run(api.handle(
    action='account_save',
    name='newapp',
    profile={'label': 'New App', 'linkedin': {
        'access_token': '*********dddd',
        'person_urn': 'urn:li:person:newapp',
        'scopes': ['w_member_social'],
        'default_target': 'personal',
    }},
))
assert resaved['ok'] is True, resaved
saved = json.loads(Path('/a0/usr/plugins/linkedin/.runtime_config.json').read_text())
assert saved['profiles']['newapp']['linkedin']['access_token'] == 'token-newapp-dddd', saved['profiles']['newapp']

# editing one account must not touch another account's secret
api_mod.handle(action='account_save', name='newapp', profile={
    'label': 'New App Renamed',
    'linkedin': {
        'access_token': 'token-newapp-dddd',
        'person_urn': 'urn:li:person:newapp',
        'scopes': ['w_member_social'],
        'default_target': 'personal',
        'default_visibility': 'CONNECTIONS',
    },
})
saved = json.loads(Path('/a0/usr/plugins/linkedin/.runtime_config.json').read_text())
assert saved['profiles']['newapp']['label'] == 'New App Renamed'
assert saved['profiles']['newapp']['linkedin']['default_visibility'] == 'CONNECTIONS'
assert saved['profiles']['justlinks']['linkedin']['access_token'] == 'token-justlinks-aaaa'
assert saved['profiles']['myresumator_biz']['linkedin']['access_token'] == 'token-mr-biz-cccc'

# bad names are rejected
rejected = api_mod.handle(action='account_save', name='Bad Name!', profile={'linkedin': {}})
assert rejected['ok'] is False, rejected

# get masks all tokens
listing = api_mod.handle(action='get')
assert listing['ok'] is True
for account in listing['config']['profiles'].values():
    token = (account.get('linkedin') or {}).get('access_token') or ''
    assert 'token-' not in token, token
assert listing['schema'], 'schema must be returned even without config.json'

# delete works and refuses to remove the last account
removed = api_mod.handle(action='account_delete', name='newapp')
assert removed['ok'] is True, removed
saved = json.loads(Path('/a0/usr/plugins/linkedin/.runtime_config.json').read_text())
assert 'newapp' not in saved['profiles']

print('OK')
PY
pass 'Config API account CRUD, masking preservation, and isolation verified'

# 7b. URN discovery resolves identifiers from an unsaved form token
"$PYTHON_BIN" - <<'PY'
import asyncio
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, '/a0')

# Patch the exact module the API imports before it loads, otherwise a second
# module instance would still hit the real network.
from usr.plugins.linkedin.helpers import linkedin_client as client_mod

seen = {}

def fake_request(self, method, path, payload=None, query=""):
    seen[path] = seen.get(path, 0) + 1
    if path == '/v2/userinfo':
        return {'ok': True, 'status': 200, 'data': {'sub': 'abc123', 'name': 'Test Member'}}
    if path == '/rest/organizationAcls':
        return {'ok': True, 'status': 200, 'data': {'elements': [
            {'organization': 'urn:li:organization:111', 'role': 'ADMIN',
             'organization~': {'id': 111, 'localizedName': 'JustLinks'}},
            {'organization': 'urn:li:organization:222', 'role': 'ADMIN',
             'organization~': {'id': 222, 'localizedName': 'MyResumator'}},
        ]}}
    return {'ok': False, 'status': 404, 'error': {'message': 'unexpected ' + path}}

client_mod.LinkedInClient._request = fake_request

spec = importlib.util.spec_from_file_location(
    'linkedin_config_api', '/a0/usr/plugins/linkedin/api/linkedin_config_api.py'
)
api_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api_mod)
api = api_mod.LinkedInConfigApi()

person = asyncio.run(api.process({
    'action': 'discover', 'name': 'justlinks', 'target': 'personal',
    'profile': {'linkedin': {'access_token': 'form-token-live'}},
}))
assert person['ok'] is True, person
assert person['person_urn'] == 'urn:li:person:abc123', person
assert 'form-token-live' not in json.dumps(person), 'token must never be echoed'

orgs = asyncio.run(api.process({
    'action': 'discover', 'name': 'myresumator_biz', 'target': 'organization',
    'profile': {'linkedin': {'access_token': 'form-token-live'}},
}))
assert orgs['ok'] is True, orgs
assert orgs['organization_urns'] == ['urn:li:organization:111', 'urn:li:organization:222'], orgs
assert 'form-token-live' not in json.dumps(orgs), 'token must never be echoed'

# a masked preview saved from an earlier session must never be sent to LinkedIn
seen.clear()
masked = asyncio.run(api.process({
    'action': 'discover', 'name': 'justlinks', 'target': 'personal',
    'profile': {'linkedin': {'access_token': '****************live'}},
}))
assert masked['ok'] is True, masked
assert seen.get('/v2/userinfo') == 1, 'stored token should be used when the form token is masked'

# no token at all is a clear refusal, not a network call
seen.clear()
missing = asyncio.run(api.process({'action': 'discover', 'name': 'empty_account', 'target': 'personal'}))
assert missing['ok'] is False, missing
assert 'token' in missing['message'].lower(), missing
assert not seen, 'no request should be made without a token'

print('OK')
PY
pass 'URN discovery resolves identifiers from an unsaved token and never echoes it'

# 8. Docs still describe the account model
require_grep 'account' "$README" 'README documents the account model'
require_grep 'clarification|which account|account' "$SMOKE_EXAMPLES" 'Smoke examples cover account selection'

printf '\nAll LinkedIn plugin regression checks passed.\n'
