# CSV 문서 사용법

위키는 Markdown(`.md`)을 기본으로 구성하고, CSV는 사용자 요청이 있을 때만 사용한다. 기존 CSV의 목적·열·고유 키·빈 값·날짜·상태·정렬 기준과 정본·사본의 관계를 먼저 확인한다. 파일 이름과 열 구성은 프로젝트별로 정한다.

## 프로젝트 지침에 연결

- 관리하는 CSV마다 역할, 헤더와 주요 열의 의미, 고유 키, 변경 경로, 파생 문서를 프로젝트 지침이나 관련 데이터 사전에 기록한다. 고정된 Markdown 문서 목록에 맞추지 않는다.
- 이 사용법을 프로젝트의 `wiki/CSV_GUIDE.md`로 연결하고, 에이전트 지침에서 관리 대상 CSV와 함께 참조한다. 기존 프로젝트 사용법이 있으면 그 내용을 보존하고 필요한 범위에서 함께 관리한다.
- CSV 작업 전에 qsv 설치 여부를 확인한다. qsv가 없으면 사용자에게 설치를 권유하고 환경에 맞는 방법으로 설치한다. 설치 후 `qsv --version`과 필요한 명령의 `--help`로 기능을 확인한다. 설치가 권한이나 환경 제약으로 막히면 사용자에게 알리고, 프로젝트의 기존 도구나 CSV 파서를 사용할지 정한다.

## 조회

아래 경로와 열 이름은 실제 프로젝트 값으로 바꾼다. SQL 안의 파일 경로에는 `/`를 사용하고 작은따옴표는 `''`로 이스케이프한다.

~~~powershell
qsv headers "data/ITEMS.csv" --just-names
qsv validate "data/ITEMS.csv" --quiet
qsv sqlp SKIP_INPUT "SELECT * FROM read_csv('data/ITEMS.csv', infer_schema => false) LIMIT 20" --format json --quiet
qsv sqlp SKIP_INPUT "SELECT * FROM read_csv('data/ITEMS.csv', infer_schema => false) WHERE id = '0007'" --format json --quiet
~~~

- `infer_schema => false`로 문자열을 읽어 ID·선행 0·날짜·상태 원문을 보존한다. 계산이 필요하면 해당 식에서만 명시적으로 형을 변환한다.
- 날짜의 시간대·오프셋과 빈 값의 의미를 임의로 바꾸지 않는다. 정확히 빈 문자열과 null을 구분해야 하면 `read_csv`의 빈 값 처리 옵션도 실제 파일에 맞춰 확인한다.
- `--ignore-errors`나 잘못된 행 잘라내기로 오류를 숨기지 않는다. 종료 코드와 stderr를 확인하고 조회 실패를 정상적인 빈 결과로 처리하지 않는다.
- `validate`의 구조 검증에 더해 프로젝트의 고유 키·상태·날짜 등 의미 제약도 확인한다. JSON Schema가 있으면 설치된 qsv의 `validate --help`에 따라 적용한다.

## 생성·변경

1. 사용자 요청과 프로젝트 근거로 열·열 순서·고유 키·빈 값·허용 값·인코딩을 정한다. 신규 CSV는 확정된 헤더만으로 시작할 수 있으며 예시 행을 실제 데이터로 넣지 않는다.
2. 정본을 변경하는 작업인지 파생 사본을 갱신하는 작업인지 확인한다. 프로젝트의 기존 생성·수정 도우미가 있으면 재사용한다. 외부 정본에서 만든 사본은 원본과 생성 절차를 통해 갱신한다.
3. 기존 헤더·ID·열 순서·값·인코딩·BOM과 프로젝트의 잠금 방식을 보존한다. 읽기 후 다른 작업이 원본을 바꾸었는지도 확인한다.
4. 임시 파일에서 변경한다. 단순 셀 수정에는 `qsv edit`, 행 추가에는 `qsv json`·`qsv cat` 같은 도구나 기존 CSV writer를 사용할 수 있다. 쉼표·따옴표·셀 안의 줄바꿈을 문자열 치환이나 줄 단위 편집으로 처리하지 않는다.
5. 구조, 헤더, 행 수, 키의 고유성, 수정 대상·값, 관련 문서와의 일관성을 검증한 뒤 원본을 교체한다. 검증이나 동시 변경 확인에 실패하면 기존 파일을 보존한다.

~~~powershell
qsv edit "data/ITEMS.csv" status 0 done --output "data/ITEMS.pending.csv"
qsv validate "data/ITEMS.pending.csv" --quiet
qsv sqlp SKIP_INPUT "SELECT * FROM read_csv('data/ITEMS.pending.csv', infer_schema => false) WHERE id = '0007'" --format json --quiet
~~~

이 예시는 첫 번째 데이터 행을 수정하는 형식이다. 실제로는 먼저 고유 키로 대상 행을 찾아야 한다. `qsv edit`의 행 번호는 헤더를 제외하고 0부터 시작하며, stdout·output 모드에서는 없는 행을 지정해도 원문을 반환하며 성공할 수 있다. 종료 코드만으로 성공을 판단하지 않고 대상 키와 값을 다시 확인한다. `--in-place` 대신 임시 출력을 사용한다. `sqlp`는 조회에 사용하고 SQL UPDATE로 원본을 변경하지 않는다. qsv 출력이 기존 인코딩·BOM을 유지했는지도 교체 전에 확인한다.

## 정본과 사본의 예

lecture 프로젝트는 `TASKS.csv`를 할 일의 정본으로 사용하고, `CALENDAR.csv`를 Notion 일정과 태스크에서 생성한 사본으로 관리한다. 태스크 변경은 기존 도우미로 수행한 뒤 관련 CSV·ICS를 같은 기준 자료로 갱신한다. 두 파일 모두 조회는 qsv로 수행하며 ID·날짜를 문자열로 보존한다.

이 사례에서 가져올 원칙은 정본·사본·변경 경로를 구분하는 것이다. 파일명, 열, 시간대, Notion 사용, ICS 생성은 각 프로젝트의 실제 구성에 따라 정한다. CSV 자체에는 Markdown frontmatter를 넣지 않는다.
