# npx skills로 공통 원본 설치·갱신

`npx skills`로 스킬을 검색·선택하여 `.symskill`의 저장소 묶음에 설치한다. 프로젝트 연결은 이 스킬의 `SKILL.md`에 따라 설치된 원본 폴더에 심볼릭 링크를 만든다.

## 설치 경로의 의미

CLI는 프로젝트 설치 시 작업 폴더 아래의 에이전트 스킬 경로를 사용한다. 이 워크플로우에서는 `~/.symskill/<repo-group>`을 CLI 작업 폴더로 삼는다. `--agent universal --copy`를 지정하면 선택한 스킬의 파일이 `<repo-group>/.agents/skills/<skill-name>`에 설치된다. 이 폴더가 이후 프로젝트들이 공유할 원본이다.

`--copy`는 공통 원본을 실제 파일로 설치하기 위한 옵션이다. 프로젝트에서 사용할 때는 심볼릭 링크로 연결한다. `--global`은 CLI의 사용자 전역 스킬 경로를 사용하므로 이 원본 저장소를 지정하는 옵션으로 사용하지 않는다. 실제 CLI 도움말에 없는 `--dir`, `--path` 등의 설치 경로 옵션을 만들어 쓰지 않는다.

실행 환경의 버전과 옵션은 필요할 때 `npx skills --version`, `npx skills --help`로 확인한다. Node.js/npm이 없으면 필요한 런타임을 안내하고 해당 설치 단계가 미완료임을 알린다.

## 검색과 선택

```sh
npx skills find <검색어>
npx skills add <owner/repo-or-url> --list
```

사용자가 스킬 이름을 지정했다면 그대로 선택한다. 지정하지 않았다면 목록에서 요청한 용도에 맞는 후보를 제시하고 선택을 받는다. 실제 터미널을 사용자가 조작할 수 있을 때는 `npx skills add <source> --agent universal --copy`의 대화형 선택을 사용할 수도 있다.

`--skill`에는 CLI가 표시한 이름을 전달한다. 이름이 여러 단어이면 인자로 따옴표 처리한다. 모든 스킬을 설치하라는 요청이 있을 때만 `--skill '*'`을 사용한다. `--all`은 다른 에이전트까지 설치 범위를 넓히므로 이 흐름에 사용하지 않는다.

## 선택한 스킬 설치

아래는 `vercel-labs/agent-skills`의 `web-design-guidelines`를 선택한 예시다. 출처, 묶음 이름, 선택한 스킬 이름은 요청에 맞게 바꾼다. 같은 이름의 기존 원본이 있으면 먼저 확인하여 재사용하거나 갱신한다.

macOS/Linux:

```sh
repo_group="$HOME/.symskill/vercel-labs--agent-skills"
mkdir -p "$repo_group"
(
  cd "$repo_group" || exit 1
  npx skills add vercel-labs/agent-skills --skill web-design-guidelines --agent universal --copy --yes
)
```

Windows PowerShell:

```powershell
$skillsRoot = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.symskill'
$repoGroup = Join-Path $skillsRoot 'vercel-labs--agent-skills'
New-Item -ItemType Directory -Path $repoGroup -Force -ErrorAction Stop | Out-Null
Push-Location -LiteralPath $repoGroup -ErrorAction Stop
try {
    npx skills add vercel-labs/agent-skills --skill web-design-guidelines --agent universal --copy --yes
    if ($LASTEXITCODE -ne 0) { throw 'npx skills 원본 설치 실패' }
} finally {
    Pop-Location
}
```

여러 스킬이 선택되었다면 `--skill skill-a skill-b`처럼 명시한다. `--yes`는 이미 정해진 출처와 선택으로 실행할 때 CLI 프롬프트를 생략하는 옵션이다.

설치 성공 후 실제 결과를 확인한다.

- 예시 원본: `~/.symskill/vercel-labs--agent-skills/.agents/skills/web-design-guidelines`.
- `SKILL.md`와 스킬이 사용하는 스크립트·참조 자료·에셋이 함께 설치되어 있어야 한다.
- CLI가 설치 폴더명을 정규화할 수 있으므로 출력과 실제 폴더를 확인한다.
- CLI가 생성한 `skills-lock.json` 등 출처·갱신 정보를 담은 파일은 묶음 루트에 보존한다. 생성되지 않았다면 사용한 출처와 설치 명령을 결과에 기록한다.

원본 확인이 끝나면 요청받은 프로젝트의 에이전트 스킬 경로에서 이 실제 원본 폴더로 링크를 만든다. 링크가 CLI의 일시적인 다운로드 경로나 캐시를 가리키지 않게 한다.

## npx skills update로 갱신

1. 요청받은 묶음과 갱신할 스킬을 확인하고, 설치할 때 사용한 **원본 묶음 루트**(`~/.symskill/<repo-group>`)를 작업 폴더로 선택한다. `skills-lock.json` 등 CLI의 출처 정보와 실제 설치 폴더를 확인한다. 연결된 프로젝트에서 실행하면 프로젝트의 설치 경로를 갱신하게 되므로 공통 원본 묶음에서 실행한다.
2. 기존 원본에 수동 변경이 있으면 먼저 보존하고 갱신과 충돌하는 내용을 보고한다.
3. `npx skills update <skill-name> --project --yes`로 요청한 스킬을 갱신한다. `--project`는 현재 원본 묶음의 프로젝트 설치 범위를 선택하고, `--yes`는 범위 선택 프롬프트를 생략한다. 스킬 이름을 생략하는 전체 갱신은 해당 묶음 전체의 갱신을 요청받았을 때만 사용한다.
4. 종료 코드와 CLI 출력에서 실제 갱신 결과를 확인한다. 원본 경로가 유지되는지, 프로젝트 링크를 통해 갱신된 `SKILL.md`와 리소스를 읽을 수 있는지 확인한다. CLI가 갱신한 lock 파일을 보존하고, 갱신된 스킬과 실패하거나 남은 작업을 결과에 기록한다. 실패한 갱신을 완료로 보고하지 않는다.

아래는 설치 예시의 `web-design-guidelines`를 갱신하는 워크플로우다. 묶음 이름과 스킬 이름은 확인한 실제 값으로 바꾼다.

macOS/Linux:

```sh
repo_group="$HOME/.symskill/vercel-labs--agent-skills"
(
  cd "$repo_group" || exit 1
  npx skills update web-design-guidelines --project --yes
)
```

Windows PowerShell:

```powershell
$skillsRoot = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.symskill'
$repoGroup = Join-Path $skillsRoot 'vercel-labs--agent-skills'
Push-Location -LiteralPath $repoGroup -ErrorAction Stop
try {
    npx skills update web-design-guidelines --project --yes
    if ($LASTEXITCODE -ne 0) { throw 'npx skills 원본 갱신 실패' }
} finally {
    Pop-Location
}
```

원본 묶음 루트에서 갱신 범위에 따라 다음 명령을 사용한다.

| 갱신 범위 | 명령 |
| --- | --- |
| 특정 스킬 | `npx skills update web-design-guidelines --project --yes` |
| 여러 스킬 | `npx skills update skill-a skill-b --project --yes` |
| 해당 묶음 전체 | `npx skills update --project --yes` |

출처 정보가 없거나 현재 CLI 버전에서 갱신을 지원하지 않는 경우, 출처와 선택한 스킬을 확인한 뒤 설치 때와 같은 `npx skills add <source> --skill <skill-name> --agent universal --copy --yes`로 원본 묶음에서 다시 설치한다. 일반 갱신 실패는 오류 내용을 먼저 확인하며, 재설치로 범위를 넓혀 처리하지 않는다.

원본 경로가 유지되면 프로젝트 링크를 다시 만들 필요가 없다. 원본이 이동하거나 이름이 바뀌면 `SKILL.md`의 갱신 절차에 따라 요청받은 프로젝트의 링크를 새 원본으로 연결한다.

CLI 설치·갱신의 작업 폴더는 원본 묶음으로 유지한다. 프로젝트의 수동 링크 해제는 `SKILL.md`의 해제 절차를 따른다.

## 공식 자료

- [skills CLI 문서](https://skills.sh/docs/cli)
- [공식 README의 옵션과 지원 에이전트](https://github.com/vercel-labs/skills#options)
- [공식 README의 update 명령과 범위 옵션](https://github.com/vercel-labs/skills#skills-update)
- [공식 설치 코드의 경로 처리](https://github.com/vercel-labs/skills/blob/main/src/installer.ts)
