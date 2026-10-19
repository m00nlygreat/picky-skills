---
name: symskill
description: Manage shared skill sources in ~/.symskill or install selected skills into projects by linking a specified source path directly. Use for npx skills or Git setup, repository grouping, symbolic links, updates, and unlinking on macOS, Linux, or Windows.
---

# symskill

스킬 원본을 사용자 홈의 `.symskill`에 설치해 공통 관리할 수 있다. 사용자가 특정 경로를 지정하면 그 경로를 원본으로 취급하고, 프로젝트의 스킬 경로에서 해당 스킬 폴더를 직접 가리키는 심볼릭 링크를 만든다. 이때 원본을 `.symskill`로 복사하거나 `.symskill`을 경유하지 않는다. `SKILL.md`와 `scripts`, `references`, `assets` 등 원본 폴더 전체가 링크를 통해 연결되게 한다.

## 저장 위치와 구조

- 홈은 OS가 제공하는 사용자 홈 경로로 구한다. 코드에서는 Python의 `Path.home()`이나 Node.js의 `os.homedir()`를 사용할 수 있다. 사용자 이름이나 `C:\Users\...`를 하드코딩하지 않는다.
- macOS/Linux 셸에서는 `$HOME/.symskill`, Windows PowerShell에서는 아래 경로를 사용한다. `$HOME`, `$home` 등의 기존 홈 변수를 덮어쓰지 않는다.

  ```powershell
  $skillsRoot = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.symskill'
  New-Item -ItemType Directory -Path $skillsRoot -Force -ErrorAction Stop | Out-Null
  ```

  ```sh
  skills_root="$HOME/.symskill"
  mkdir -p "$skills_root"
  ```

- 단독 스킬은 루트 바로 아래에 둘 수 있고, 여러 스킬은 저장소별 폴더에 묶을 수 있다. 지정된 구조가 없으면 `owner--repo`처럼 출처를 구분하는 이름을 사용한다. 기존 묶음이 다른 출처를 담고 있으면 별도 이름으로 설치한다.
- Git으로 설치한 저장소는 내부 구조를 유지한다. `npx skills`로 설치한 묶음은 CLI의 `.agents/skills` 구조와 lock 파일을 유지한다. 같은 저장소라도 Git checkout과 CLI 설치본은 별도 묶음으로 관리한다.

```text
<사용자 홈>/.symskill/
├── standalone-skill/
│   └── SKILL.md
├── owner--git-repo/
│   └── skills/
│       └── skill-a/
│           ├── SKILL.md
│           └── references/
└── owner--cli-repo/
    ├── skills-lock.json          # CLI가 생성한 경우 보존
    └── .agents/skills/
        └── skill-b/
            ├── SKILL.md
            └── scripts/

<프로젝트>/<에이전트의 스킬 경로>/
└── skill-b -> <사용자 홈>/.symskill/owner--cli-repo/.agents/skills/skill-b

<특정 원본 경로>/skill-b/
├── SKILL.md
└── references/

<프로젝트>/<에이전트의 스킬 경로>/
└── skill-b -> <특정 원본 경로>/skill-b
```

## 원본 설치와 선택

1. 요청에서 특정 원본 경로, 선택할 스킬, 프로젝트, 대상 에이전트를 확인한다. 특정 로컬 경로가 주어지면 이를 최우선 정본으로 삼는다. 프로젝트 설치 요청이면 해당 경로의 스킬 폴더를 프로젝트에 직접 심볼릭 링크하며, 같은 내용이 이미 `.symskill`에 있더라도 `.symskill` 사본을 대신 연결하지 않는다.
2. 지정 경로 자체에 `SKILL.md`가 있으면 그 폴더를 스킬 원본으로 사용한다. 저장소 루트처럼 `SKILL.md`가 없으면 하위에서 요청한 스킬 이름의 폴더와 `SKILL.md`를 찾아 해당 스킬 폴더를 원본으로 정한다. `.git`과 생성물 디렉터리는 검색에서 제외한다.
3. 특정 원본 경로가 없고 원격 출처에서 설치하거나 공통 원본 설치를 요청한 경우에만 `.symskill`을 원본 저장소로 사용한다. `npx skills`를 이용할 때는 [references/npx-skills.md](references/npx-skills.md)를 읽고 선택한 스킬만 설치한다.
4. 저장소 전체를 Git으로 공통 관리하려는 요청은 `git clone <repo-url> "<skills-root>/<repo-group>"`으로 설치한다. 이미 해당 출처의 checkout이 있으면 재사용한다. 로컬 경로가 명시된 경우에는 요청에 복사 또는 공통 저장소 설치가 따로 포함되지 않는 한 해당 경로를 `.symskill`로 복사하지 않는다.
5. 원본으로 정한 각 실제 스킬 폴더에 `SKILL.md`가 있는지 확인하고, 그 폴더 전체를 링크 대상으로 사용한다.

원본 위치의 기존 파일이나 다른 출처 저장소를 덮어써서 신규 원본 설치를 하지 않는다. 지정한 원본 경로가 이미 존재하면 그 위치를 재사용한다. 목적지 처리는 아래 프로젝트 연결 규칙을 따른다.

## 프로젝트에 연결

프로젝트의 설정과 요청한 에이전트를 확인하여 실제 스킬 경로를 정한다. `.agents/skills` 또는 `.claude/skills` 등을 사용할 수 있지만, 여러 에이전트에 연결하는 것은 요청한 범위에 따른다. 저장소 묶음 전체가 아니라 선택한 각 스킬 폴더를 연결한다. 특정 원본 경로를 받았다면 프로젝트 링크의 대상은 그 경로 아래에서 확인한 스킬 폴더 자체다. `.symskill` 사본을 중간 대상으로 삼지 않는다.

연결 전 다음을 확인한다.

- 원본은 요청에 따라 지정 경로의 스킬 폴더 또는 `.symskill` 아래의 스킬 폴더다. `SKILL.md`와 필요한 리소스를 함께 포함해야 한다.
- 원본과 링크 위치는 절대 경로로 계산한다. 기존 부모 폴더가 링크라면 실제 쓰기 위치도 확인한다.
- 목적지에 같은 원본으로 향하는 링크가 이미 있으면 완료된 것으로 처리한다.
- 내용이 같더라도 일반 폴더는 심볼릭 링크가 아니므로 링크 설치가 완료된 것으로 보지 않는다. 사용자가 특정 원본 경로를 지정해 링크 설치를 요청한 경우, 기존 경로가 이 스킬이 만든 사본임을 확인하면 그 사본을 링크로 교체한다. 출처를 알 수 없거나 사용자 파일이 포함된 경로라면 보존하고 충돌을 보고한다. 다른 원본으로 향하는 링크도 임의로 덮어쓰지 않는다. 깨진 링크도 기존 링크로 인식한다.

아래 예시는 프로젝트 루트에서 실행한다. 특정 원본 경로가 있으면 해당 스킬 폴더의 절대 경로를 직접 지정한다. 저장소 루트를 받았다면 저장소 자체가 아니라 그 안에서 찾은 각 스킬 폴더를 대상으로 삼는다. 목적지의 출처와 링크 여부를 확인하고, 같은 원본을 가리키는 링크는 재사용한다. 사용자가 이 원본을 지정해 설치를 요청했고 기존 목적지가 이 스킬이 만든 사본이면 해당 사본을 심볼릭 링크로 교체한다. 알 수 없는 파일이 있는 일반 폴더나 다른 원본 링크는 보존하고 충돌을 알린다.

macOS/Linux:

```sh
source_dir="/path/to/skills/skill-b"
link_dir="$PWD/.agents/skills"
mkdir -p "$link_dir"
ln -s "$source_dir" "$link_dir/skill-b"
```

Windows PowerShell:

```powershell
$sourcePath = [IO.Path]::GetFullPath('C:\path\to\skills\skill-b')
$linkDirectory = Join-Path (Get-Location).Path '.agents/skills'
$linkPath = Join-Path $linkDirectory 'skill-b'
New-Item -ItemType Directory -Path $linkDirectory -Force -ErrorAction Stop | Out-Null
New-Item -ItemType SymbolicLink -Path $linkPath -Target $sourcePath -ErrorAction Stop
```

특정 경로가 주어지지 않은 경우에만 `$sourcePath` 또는 `source_dir`를 앞의 `.symskill` 구조에 있는 실제 스킬 원본으로 지정한다.

Windows에서 심볼릭 링크 권한 오류가 발생하면 현재 환경에서 생성할 수 없음을 보고한다. [PowerShell 공식 문서](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/new-item#-itemtype)에 따라 Developer Mode나 권한 있는 실행 환경이 필요할 수 있다. 링크 생성 실패를 복사 설치로 바꾸어 완료했다고 보고하지 않는다. 사용자가 디렉터리 junction 대안을 선택하면 그 방식으로 연결하고 실제 링크 종류를 알린다.

생성 후 링크 종류가 실제 `SymbolicLink`인지와 해석된 대상 경로가 요청한 원본 폴더와 정확히 일치하는지 확인한다. 링크를 통해 `SKILL.md`와 필요한 리소스도 읽을 수 있어야 한다. 파일 내용 비교만으로 링크 완료를 판단하지 않는다. 홈 경로를 담은 링크는 해당 컴퓨터에 종속되므로 요청 없이 커밋하거나 팀 공용 설치로 배포하지 않는다.

## 원본 갱신

- Git 묶음은 출처와 작업 상태를 확인한 뒤 `git -C "<repo-group>" pull --ff-only`로 갱신한다. 로컬 변경이나 분기 충돌이 있으면 보존하고 충돌 내용을 보고한다.
- CLI 묶음은 해당 원본 묶음 루트(`~/.symskill/<repo-group>`)에서 `npx skills update <skill-name> --project --yes`로 요청한 스킬을 갱신한다. 묶음 전체의 갱신을 요청받으면 `npx skills update --project --yes`를 사용한다. 작업 폴더 선택, 수동 변경 보존, OS별 실행 예시는 [references/npx-skills.md](references/npx-skills.md)의 갱신 워크플로우를 따른다.
- 특정 경로를 원본으로 직접 링크했다면 그 경로의 변경은 프로젝트에 바로 반영되므로 CLI 갱신이나 사본 복사를 하지 않는다. 원본 경로가 이동하거나 스킬 이름이 바뀌면 요청받은 프로젝트의 링크를 새 원본으로 연결한다.
- 갱신 후 연결을 통해 변경된 원본과 리소스를 읽을 수 있는지 확인하고, 해당 원본을 쓰는 프로젝트들에 변경이 반영된다는 점을 결과에 알린다.

## 프로젝트에서 해제

프로젝트에서 스킬을 제거하는 요청은 해당 링크를 해제한다. 링크 자체의 파일 정보와 대상 경로를 확인한 뒤 macOS/Linux의 `unlink` 또는 PowerShell의 `Remove-Item -LiteralPath`로 링크만 제거한다. 원본 경로에 삭제 명령을 실행하거나 링크를 따라 재귀 삭제하지 않는다. 일반 폴더로 설치된 스킬은 링크로 간주하여 지우지 않는다.

공통 원본 삭제는 프로젝트 링크 해제와 별도 작업이다. 원본 삭제 요청이 있으면 알려진 프로젝트의 연결과 삭제 범위를 확인하여 수행하고, 확인한 연결 외에 사용 중인 프로젝트가 있을 수 있음을 알린다. 요청 없이 홈 전체를 검색하지 않는다.

## 결과 보고

설치·갱신한 원본 위치와 출처, 선택한 스킬, 프로젝트의 `링크 경로 → 원본 경로`, 실제 링크 종류, 확인 결과를 간단히 알려준다. 특정 경로를 직접 원본으로 사용했는지 `.symskill`에 공통 원본을 설치했는지 구분한다. 원본 설치와 프로젝트 연결 중 어디까지 완료됐는지, 충돌이나 권한 오류로 남은 작업이 있다면 무엇인지 명확히 기록한다.
