# Copyright 2026 Jarryd Adaens
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

$ErrorActionPreference = "Stop"
. "$PSScriptRoot/readme-guard-common.ps1"

# PreToolUse guardrail on the Write tool. Denies creating or overwriting any file
# whose name is "readme.md" (any capitalization) unless it sits at the project
# root, so the codebase keeps a single, unambiguous README instead of dozens of
# same-named files. The denial names a prefixed alternative so the agent
# self-corrects. Any internal error fails OPEN (exit 0) so a hook bug can never
# block every Write.

try {
    $hook = Read-HookPayload
    if ($null -eq $hook) { exit 0 }

    $filePath = $hook.tool_input.file_path
    if ([string]::IsNullOrWhiteSpace($filePath)) { exit 0 }

    $root = Get-ProjectRoot $hook
    $config = Get-GuardConfig $root
    if (Test-ConfigDisabled $config) { exit 0 }

    $abs = Resolve-AbsolutePath $filePath $root
    if (-not (Test-ForbiddenReadme $abs $root)) { exit 0 }

    $rel = Get-RelativePosixPath $abs $root
    if (Test-AllowedByConfig $rel $config) { exit 0 }

    $suggested = Get-SuggestedName $abs
    $reason = "readme-name-guardrail: creating '$rel' is forbidden. The name 'readme.md' " +
        "(any capitalization) is reserved for the single project-root README; extra files " +
        "with that exact name pile up and crowd terminal file references. Give it a " +
        "descriptive prefix instead - e.g. '$suggested' - then retry. A prefixed name like " +
        "that is allowed anywhere."
    Deny-PreToolUse $reason $hook
    exit 0
}
catch {
    exit 0  # internal error: fail open so the guardrail never blocks all Write
}
