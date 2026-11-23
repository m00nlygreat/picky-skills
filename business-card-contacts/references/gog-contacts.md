# gog 연락처 절차

로컬 `gog v0.34.1`의 도움말과 공식 문서를 기준으로 작성했다. 다른 버전에서는 필요한 명령의 `--help`를 우선 확인한다. 아래 값은 실행 형식을 설명하는 가상 예시다.

## 준비

```powershell
gog --version
gog contacts create --help
gog contacts update --help
gog auth list --json --no-input
```

저장된 계정에 `moonlygreat@gmail.com`과 `contacts` 서비스 권한이 있는지 확인한다. 계정·권한이 부족할 때는 상태를 설명하고 다음 인증 명령을 안내한다. 기존 계정의 다른 서비스 권한을 축소하거나 인증 설정을 임의로 교체하지 않는다. 새 동의가 필요하면 사용자가 Google 인증 화면을 완료해야 한다.

```powershell
gog auth add moonlygreat@gmail.com --services contacts
```

## 검색·조회

각 쿼리를 별도 검색한다. 하나의 검색에 이메일·전화·이름을 모두 이어 붙이지 않는다.

```powershell
gog --account moonlygreat@gmail.com --readonly --json --no-input contacts search 'gildong@example.com' --max 30
gog --account moonlygreat@gmail.com --readonly --json --no-input contacts search '01012345678' --max 30
gog --account moonlygreat@gmail.com --readonly --json --no-input contacts search '홍길동' --max 30
gog --account moonlygreat@gmail.com --readonly --json --no-input contacts get 'people/c123456'
```

검색 결과의 `contacts[]`는 `resource`, 대표 이름·이메일·전화 등 요약을 반환한다. `get`의 `contact`는 `resourceName`, ETag와 필드 배열을 반환한다. 후보별 조회 결과를 재사용한다. 결과 수가 한도에 닿으면 이메일 등 더 구체적인 쿼리로 좁힌다.

## 신규 생성

`create`에는 `--given`이 필요하다. 성을 구분하지 않을 때는 전체 이름을 넣고 `--family`를 생략한다. 아래 옵션 중 명함에 없는 항목은 옵션 자체를 제외한다.

```powershell
gog --account moonlygreat@gmail.com --json --no-input contacts create --given '홍길동' --email 'gildong@example.com' --phone '010-1234-5678' --org '예시회사' --title '팀장'
```

주소·홈페이지·메모는 각각 `--address`, `--url`, `--note`로 전달할 수 있다. `--email`과 `--phone`은 각각 단일 값이다. 복수 값이나 유형·부서가 필요하면 생성한 동일 ID를 JSON으로 갱신한다.

## JSON 갱신

`get` 응답의 `contact`에서 `resourceName`, `etag`, `metadata`를 복사하고 **변경할 필드만** 추가해 갱신 객체를 만든다. 나머지 최상위 필드는 넣지 않는다. `metadata`의 CONTACT 소스 ETag도 유지해야 한다. `gog`가 현재 소스 ETag와 비교한다.

아래는 기존 업무전화에 휴대전화와 팩스를 추가하고, 같은 회사의 부서를 채우는 예다. 실제 값과 ETag는 반드시 직전 조회에서 가져온다. 이미 존재하는 배열 항목과 각 항목의 쓰기 가능한 속성을 모두 보존한다.

```json
{
  "resourceName": "people/c123456",
  "etag": "CURRENT_PERSON_ETAG",
  "metadata": {
    "sources": [
      {"type": "CONTACT", "id": "123456", "etag": "CURRENT_CONTACT_ETAG"}
    ]
  },
  "phoneNumbers": [
    {"value": "02-123-4567", "type": "work"},
    {"value": "010-1234-5678", "type": "mobile"},
    {"value": "02-123-4568", "type": "workFax"}
  ],
  "organizations": [
    {"name": "예시회사", "department": "교육팀", "title": "팀장"}
  ]
}
```

필요한 필드의 항목 형식은 다음과 같다.

| 필드 | 새 항목 예시 |
| --- | --- |
| `emailAddresses` | `{"value":"gildong@example.com","type":"work"}` |
| `phoneNumbers` | `{"value":"010-1234-5678","type":"mobile"}` |
| `addresses` | `{"formattedValue":"서울특별시 예시로 123, 4층","type":"work"}` |
| `urls` | `{"value":"https://example.com","type":"work"}` |
| `biographies` | `{"value":"기존 메모\n영문 이름: Gildong Hong","contentType":"TEXT_PLAIN"}` |

`names`와 `biographies`는 연락처 소스당 한 항목으로 유지한다. 기존 메모는 같은 `value` 안에서 보존한다. 수정하는 배열은 보내는 내용으로 교체되므로 새 항목만 보내면 기존 항목이 사라질 수 있다. 빈 문자열·`[]`·`null`을 누락 정보의 대용으로 전송하지 않는다. 단일 값 `--email`, `--phone`, `--note`로 기존 복수 값이나 메모를 덮어쓰지 않는다.

갱신 객체를 UTF-8 BOM 없는 JSON 임시 파일로 저장하고 실행한다. 임시 파일 경로는 생성할 때 기록한 정확한 경로를 사용한다.

```powershell
gog --account moonlygreat@gmail.com --json --no-input contacts update 'people/c123456' --from-file 'C:\path\to\contact-update.json'
gog --account moonlygreat@gmail.com --readonly --json --no-input contacts get 'people/c123456'
```

`--ignore-etag`는 사용하지 않는다. 오류가 났을 때는 `SKILL.md`의 재조회·재시도 기준을 따른다. 사진이나 연락처 JSON을 스킬 저장소에 보관하지 않고, 작업에 사용한 임시 파일만 완료 후 제거한다.

## 셸 전달과 점검

명함의 회사명·주소·메모에는 따옴표나 셸 문자가 들어갈 수 있다. 값을 명령 문자열에 그대로 끼워 넣지 않는다. PowerShell에서는 작은따옴표 문자열의 내부 작은따옴표를 두 번 써서 인용하거나, 값이 든 인자 배열로 전달한다. JSON은 직렬화 도구와 UTF-8 파일 쓰기를 사용한다.

명령 구문만 점검할 때는 가상 값으로 `--dry-run`을 추가한다. 이는 실제 등록 성공이나 API 저장 검증을 대신하지 않는다. 연락처 목록을 조회하거나 시험용 연락처를 생성할 필요는 없다.

## 공식 자료

- [gog contacts create](https://gogcli.sh/commands/gog-contacts-create.html)
- [gog contacts update](https://gogcli.sh/commands/gog-contacts-update.html)
- [JSON 갱신 형식](https://github.com/steipete/gogcli/blob/main/docs/contacts-json-update.md)
- [Google People 필드](https://developers.google.com/people/api/rest/v1/people)
