---
name: symskill
description: Manage shared skill sources under the user's ~/.symskill directory and link selected skill folders into projects. Use for central installation with npx skills or Git, repository grouping, symbolic links, shared updates, and unlinking on macOS, Linux, or Windows.
---

# symskill

스킬 원본을 사용자 홈의 `.symskill`에 설치하고, 프로젝트마다 필요한 스킬 폴더를 심볼릭 링크로 연결한다. 원본의 `SKILL.md`, `scripts`, `references`, `assets`를 함께 관리하여 원본 갱신이 연결된 프로젝트에 반영되게 한다.

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
```

## 원본 설치와 선택

1. 요청에서 출처, 선택할 스킬, 프로젝트, 대상 에이전트를 확인한다. 원본 설치만 요청했다면 공통 저장소에 설치하고 결과를 알려준다. 프로젝트 연결도 요청했다면 설치 후 연결까지 진행한다.
2. 기존 원본을 먼저 확인한다. 목록은 `.symskill` 아래의 `SKILL.md`를 찾아 작성하며, `.git`은 제외한다. 저장소 루트에 스킬이 있다고 가정하지 않는다.
3. `npx skills`를 이용할 때는 [references/npx-skills.md](references/npx-skills.md)를 읽는다. 검색하거나 저장소의 스킬 목록을 확인하고, 선택한 스킬만 원본 묶음에 설치하는 기본 경로다.
4. 저장소 전체를 Git으로 관리하려는 요청은 `git clone <repo-url> "<skills-root>/<repo-group>"`으로 설치한다. 이미 해당 출처의 checkout이 있으면 재사용한다. 로컬 스킬 폴더를 가져오는 요청은 필요한 파일 전체를 공통 저장소에 복사한다.
5. 설치된 각 스킬의 실제 폴더에 `SKILL.md`가 있는지 확인한다. 설치 명령이 출력한 경로와 디렉터리 구조를 확인하여 링크의 원본을 정한다.

원본의 기존 파일이나 다른 저장소를 덮어써서 새 설치를 처리하지 않는다. 이미 같은 스킬이 있으면 재사용하고, 갱신 요청은 아래 갱신 절차로 처리한다.

## 프로젝트에 연결

프로젝트의 설정과 요청한 에이전트를 확인하여 실제 스킬 경로를 정한다. `.agents/skills` 또는 `.claude/skills` 등을 사용할 수 있지만, 여러 에이전트에 연결하는 것은 요청한 범위에 따른다. 저장소 묶음 전체가 아니라 선택한 각 스킬 폴더를 연결한다.

연결 전 다음을 확인한다.

- 원본은 `.symskill` 아래의 스킬 폴더이며, `SKILL.md`와 필요한 리소스를 함께 포함한다.
- 원본과 링크 위치는 절대 경로로 계산한다. 기존 부모 폴더가 링크라면 실제 쓰기 위치도 확인한다.
- 목적지에 같은 원본으로 향하는 링크가 이미 있으면 완료된 것으로 처리한다.
- 다른 원본으로 향하는 링크, 일반 파일, 일반 폴더가 있으면 기존 내용과 출처를 확인한다. 요청에 교체나 이전이 포함되지 않았으면 충돌을 보고하고 해당 경로의 교체 여부를 묻는다. 깨진 링크도 기존 링크로 인식한다.

아래 예시는 프로젝트 루트에서 실행한다. 원본 상대 경로와 에이전트 스킬 경로는 확인한 실제 값으로 바꾼다. 목적지가 비어 있음을 확인한 뒤 생성하며 강제 덮어쓰기 옵션은 사용하지 않는다.

macOS/Linux:

```sh
source_dir="$HOME/.symskill/owner--cli-repo/.agents/skills/skill-b"
link_dir="$PWD/.agents/skills"
mkdir -p "$link_dir"
ln -s "$source_dir" "$link_dir/skill-b"
```

Windows PowerShell:

```powershell
$skillsRoot = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.symskill'
$sourcePath = Join-Path $skillsRoot 'owner--cli-repo/.agents/skills/skill-b'
$linkDirectory = Join-Path (Get-Location).Path '.agents/skills'
$linkPath = Join-Path $linkDirectory 'skill-b'
New-Item -ItemType Directory -Path $linkDirectory -Force -ErrorAction Stop | Out-Null
New-Item -ItemType SymbolicLink -Path $linkPath -Target $sourcePath -ErrorAction Stop
```

Windows에서 심볼릭 링크 권한 오류가 발생하면 현재 환경에서 생성할 수 없음을 보고한다. [PowerShell 공식 문서](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/new-item#-itemtype)에 따라 Developer Mode나 권한 있는 실행 환경이 필요할 수 있다. 링크 생성 실패를 복사 설치로 바꾸어 완료했다고 보고하지 않는다. 사용자가 디렉터리 junction 대안을 선택하면 그 방식으로 연결하고 실제 링크 종류를 알린다.

생성 후 링크를 해석했을 때 원본 폴더로 연결되는지, 링크를 통해 `SKILL.md`와 필요한 리소스를 읽을 수 있는지 확인한다. 홈 경로를 담은 링크는 해당 컴퓨터에 종속되므로 요청 없이 커밋하거나 팀 공용 설치로 배포하지 않는다.

## 원본 갱신

- Git 묶음은 출처와 작업 상태를 확인한 뒤 `git -C "<repo-group>" pull --ff-only`로 갱신한다. 로컬 변경이나 분기 충돌이 있으면 보존하고 충돌 내용을 보고한다.
- CLI 묶음은 해당 원본 묶음 루트(`~/.symskill/<repo-group>`)에서 `npx skills update <skill-name> --project --yes`로 요청한 스킬을 갱신한다. 묶음 전체의 갱신을 요청받으면 `npx skills update --project --yes`를 사용한다. 작업 폴더 선택, 수동 변경 보존, OS별 실행 예시는 [references/npx-skills.md](references/npx-skills.md)의 갱신 워크플로우를 따른다.
- 원본 경로가 유지되면 프로젝트 링크를 다시 만들 필요가 없다. 스킬이 이동하거나 이름이 바뀌면 요청받은 프로젝트의 링크를 새 원본으로 연결한다.
- 갱신 후 연결을 통해 변경된 원본과 리소스를 읽을 수 있는지 확인하고, 해당 원본을 쓰는 프로젝트들에 변경이 반영된다는 점을 결과에 알린다.

## 프로젝트에서 해제

프로젝트에서 스킬을 제거하는 요청은 해당 링크를 해제한다. 링크 자체의 파일 정보와 대상 경로를 확인한 뒤 macOS/Linux의 `unlink` 또는 PowerShell의 `Remove-Item -LiteralPath`로 링크만 제거한다. 원본 경로에 삭제 명령을 실행하거나 링크를 따라 재귀 삭제하지 않는다. 일반 폴더로 설치된 스킬은 링크로 간주하여 지우지 않는다.

공통 원본 삭제는 프로젝트 링크 해제와 별도 작업이다. 원본 삭제 요청이 있으면 알려진 프로젝트의 연결과 삭제 범위를 확인하여 수행하고, 확인한 연결 외에 사용 중인 프로젝트가 있을 수 있음을 알린다. 요청 없이 홈 전체를 검색하지 않는다.

## 결과 보고

설치·갱신한 원본 위치와 출처, 선택한 스킬, 프로젝트의 `링크 경로 → 원본 경로`, 실제 링크 종류, 확인 결과를 간단히 알려준다. 원본 설치와 프로젝트 연결 중 어디까지 완료됐는지, 충돌이나 권한 오류로 남은 작업이 있다면 무엇인지 명확히 기록한다.
