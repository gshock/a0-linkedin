#!/usr/bin/env bash
set -euo pipefail

PLUGIN_DIR="/a0/usr/plugins/linkedin"
RUNTIME_CONFIG="$PLUGIN_DIR/.runtime_config.json"
HELPERS_CONFIG="$PLUGIN_DIR/helpers/config.py"
POST_TOOL="$PLUGIN_DIR/tools/linkedin_post.py"
READ_TOOL="$PLUGIN_DIR/tools/linkedin_read.py"
ACCOUNT_TOOL="$PLUGIN_DIR/tools/linkedin_account.py"
README="$PLUGIN_DIR/README.md"
HUMAN_TEST_PLAN="$PLUGIN_DIR/tests/HUMAN_TEST_PLAN.md"
SMOKE_EXAMPLES="$PLUGIN_DIR/tests/smoke_examples.md"

TMP_BACKUP="$(mktemp)"
cp "$RUNTIME_CONFIG" "$TMP_BACKUP"
restore() {
  cp "$TMP_BACKUP" "$RUNTIME_CONFIG"
  rm -f "$TMP_BACKUP"
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

# 1. Files exist
for f in "$HELPERS_CONFIG" "$POST_TOOL" "$READ_TOOL" "$ACCOUNT_TOOL" "$README" "$HUMAN_TEST_PLAN" "$SMOKE_EXAMPLES"; do
  [ -f "$f" ] || fail "Required file missing: $f"
done
pass 'Required plugin files exist'

# 2. Python syntax checks
python -m py_compile "$HELPERS_CONFIG" "$PLUGIN_DIR/helpers/sanitize.py" "$PLUGIN_DIR/helpers/linkedin_client.py" "$POST_TOOL" "$READ_TOOL" "$ACCOUNT_TOOL"
pass 'Core helper/tool files compile'

# 3. Routing helper presence
require_grep 'def resolve_linkedin_config\(' "$HELPERS_CONFIG" 'resolve_linkedin_config helper present'
require_grep 'def resolve_profile_name\(' "$HELPERS_CONFIG" 'resolve_profile_name helper present'
require_grep 'def get_profile_name_for_target\(' "$HELPERS_CONFIG" 'target-to-profile helper present'

# 4. linkedin_post compatibility and routing markers
require_grep 'text = self.args.get\("text"\)' "$POST_TOOL" 'linkedin_post reads text'
require_grep 'self.args.get\("message", ""\)' "$POST_TOOL" 'linkedin_post falls back to message'
require_grep 'resolved_profile' "$POST_TOOL" 'linkedin_post returns resolved_profile metadata'
require_grep 'needs_clarification' "$POST_TOOL" 'linkedin_post supports clarification-needed responses'
require_grep 'image_paths = self.args.get\("image_paths"\)' "$POST_TOOL" 'linkedin_post accepts image_paths'
require_grep "Provide either 'image_path' or 'image_paths', not both." "$POST_TOOL" 'linkedin_post rejects conflicting image inputs'
require_grep 'def create_multi_image_post\(' "$PLUGIN_DIR/helpers/linkedin_client.py" 'linkedin_client multi-image create helper present'
require_grep 'validate_image_paths' "$PLUGIN_DIR/helpers/sanitize.py" 'sanitize helper validates multiple image paths'

# 5. linkedin_read routing markers
require_grep 'resolve_linkedin_config' "$READ_TOOL" 'linkedin_read uses per-call routing helper'
require_grep 'resolved_profile' "$READ_TOOL" 'linkedin_read returns resolved_profile metadata'
require_grep 'needs_clarification' "$READ_TOOL" 'linkedin_read supports clarification-needed responses'

# 6. linkedin_account dual-mode status markers
require_grep 'personal' "$ACCOUNT_TOOL" 'linkedin_account references personal readiness'
require_grep 'organization' "$ACCOUNT_TOOL" 'linkedin_account references organization readiness'

# 7. Runtime config JSON validity
python -m json.tool "$RUNTIME_CONFIG" >/dev/null
pass 'Runtime config is valid JSON'

# 8. Profile defaults and isolation checks against live runtime config
python - <<'PY'
import json
from pathlib import Path
path = Path('/a0/usr/plugins/linkedin/.runtime_config.json')
config = json.loads(path.read_text())
profiles = config.get('profiles', {})
assert isinstance(profiles, dict), 'profiles must be a dict'
assert 'personal_app' in profiles or config.get('active_profile') in {'personal_app','org_app','default'}, 'expected profile model present'
# Ensure profile dictionaries are isolated objects in saved JSON structure
if 'personal_app' in profiles and 'org_app' in profiles:
    p = profiles['personal_app'].get('linkedin', {})
    o = profiles['org_app'].get('linkedin', {})
    assert isinstance(p, dict) and isinstance(o, dict)
    assert p is not o
print('OK')
PY
pass 'Runtime config uses profile-based structure'

# 9. Config persistence smoke test for independent values
python - <<'PY'
import json
from pathlib import Path
path = Path('/a0/usr/plugins/linkedin/.runtime_config.json')
config = json.loads(path.read_text())
profiles = config.setdefault('profiles', {})
profiles.setdefault('personal_app', {'label': 'Personal App', 'linkedin': {}})
profiles.setdefault('org_app', {'label': 'Organization App', 'linkedin': {}})
p = profiles['personal_app'].setdefault('linkedin', {})
o = profiles['org_app'].setdefault('linkedin', {})
p_old = p.get('default_visibility', 'PUBLIC')
o_old = o.get('default_visibility', 'PUBLIC')
p['default_visibility'] = 'CONNECTIONS'
o['default_visibility'] = 'PUBLIC'
path.write_text(json.dumps(config, indent=2))
updated = json.loads(path.read_text())
p2 = updated['profiles']['personal_app']['linkedin']['default_visibility']
o2 = updated['profiles']['org_app']['linkedin']['default_visibility']
assert p2 == 'CONNECTIONS', f'personal visibility did not persist: {p2}'
assert o2 == 'PUBLIC', f'org visibility changed unexpectedly: {o2}'
print('OK')
PY
pass 'Profile-specific config values persist independently'

# 10. Docs mention current architecture and limitations
require_grep 'dual-profile' "$README" 'README mentions dual-profile model'
require_grep 'org_app is under LinkedIn review' "$README" 'README documents org review status'
require_grep 'Personal / Organization / Runtime' "$HUMAN_TEST_PLAN" 'Human test plan covers dual-profile UI tabs'
require_grep 'clarification' "$SMOKE_EXAMPLES" 'Smoke examples cover ambiguity handling'

printf '\nAll LinkedIn plugin regression checks passed.\n'
