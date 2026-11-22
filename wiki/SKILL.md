---
name: wiki
description: Manage project documents with docs/ as the default location and Markdown as the default format. Use CSV only when requested.
---

# Wiki

프로젝트 문서를 생성·정리·연결·갱신한다. 새 문서는 기본적으로 `./docs/`에 Markdown으로 작성하고, CSV는 사용자가 요청했을 때만 다룬다.

## 문서 관리

- `LOG`, `TERMS`, `REQUIREMENT`, `MVP`는 결정·용어·요구사항·범위를 정리할 때 고려할 수 있는 예시다. 고정 모듈이나 필수 선택 목록으로 취급하지 않는다.
- README, 설계, 운영, 조사, 일정, 데이터 사전 등 기존 프로젝트 문서는 역할과 위치를 존중해 관리한다.
- 문서의 이름·종류·개수·형식·위치는 프로젝트와 사용자 요청에 맞게 정한다. 기존 문서를 정해진 이름·형식·폴더로 일괄 변환하거나 옮기지 않는다.
- 변경 정보는 해당 역할을 맡은 문서에 반영하고, 에이전트 지침에 관리 범위·관련 문서의 상대 경로 링크·역할·관리 방법을 연결한다.
- 기존 YAML frontmatter와 사용자 작성 내용은 보존한다. 원본 자료 폴더는 사용자가 요청하지 않는 한 수정하지 않는다.
- CSV를 요청받으면 [CSV 사용법](references/csv.md)을 읽고 열·고유 키·정본과 사본·기존 도우미를 확인한다. 신규 열은 요청과 프로젝트 근거에 따라 정한다.

## 초기화·연결 도우미

`scripts/init_wiki.py`는 반복적인 파일 생성과 지침 연결을 돕는 선택 도구다. 문서 관리 범위를 도우미나 내장 템플릿 목록으로 한정하지 않는다.

- 확장자 없는 문서명만 주면 `docs/<이름>.md`를 사용한다. 경로를 지정하면 해당 위치를 사용한다.
- 내장 템플릿과 이름이 맞는 Markdown에는 해당 템플릿을 사용한다. 다른 Markdown은 제목을 가진 시작 문서를 만든다. 기존 형식의 문서는 해당 형식의 도구로 작성·수정하고, 도우미에는 기존 경로를 넘겨 지침만 연결할 수 있다.
- CSV는 사용자 요청이 있을 때만 사용한다. 신규 CSV에는 헤더를 명시하고, 기존 CSV는 보존한다. CSV를 관리하면 `docs/CSV_GUIDE.md`를 연결한다.
- 인자 없이 실행하면 기존 `docs/` 문서와 일반 관리 지침을 연결한다.
- `--force`는 사용자가 요청한 Markdown 시작 문서 덮어쓰기에만 사용한다.

~~~bash
python path/to/wiki/scripts/init_wiki.py --project-root .
python path/to/wiki/scripts/init_wiki.py --project-root . LOG docs/ARCHITECTURE.md README.md
python path/to/wiki/scripts/init_wiki.py --project-root . docs/TERMS.csv --csv-header docs/TERMS.csv "name,label,meaning"
~~~

## 에이전트 지침 연결

- 기존 `AGENTS.md` 또는 `AGENTs.md`를 사용하고, 없으면 `AGENTS.md`를 만든다.
- `## 위키 관리`에 프로젝트와 함께 관리하는 문서가 대상임을 명시한다. 관련 문서·역할·관리 방법을 연결하며 다른 섹션과 사용자 작성 지침은 보존한다. 같은 규칙을 중복 추가하지 않는다.
- 문서 참조에는 프로젝트 기준 상대 경로의 Markdown 링크를 사용한다.
- CSV를 다루면 [CSV 사용법](references/csv.md)을 프로젝트에 연결하고, qsv 조회·검증, 문자열 보존, 정본·사본 구분과 변경 절차를 지침에 반영한다.
