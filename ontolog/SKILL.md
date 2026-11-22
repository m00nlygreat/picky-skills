---
name: ontolog
description: Set up, inspect, design, update, and validate project ontologies in ONTOLOGY.yaml, including source locations, relationship semantics, and entity specifications.
---

# Ontolog

- 정본은 프로젝트 루트의 `ONTOLOGY.yaml`이다. 온톨로지를 사용하는 프로젝트의 모든 작업을 시작할 때 정본 전체를 읽고 작업 맥락에 포함한다. 개념을 이름으로 찾고 요청에 필요한 관계와 최상위 소스 참조를 따라간다.
- 채팅에서 처음 스킬을 사용할 때 `yq`가 실행되는지 확인한다. 정본을 읽은 뒤 YAML 항목을 따로 확인할 때는 `yq`를 사용한다. 사용 불가하면 설치를 한 번 권하고, 가용한 YAML 처리기로 필요한 항목을 출력하거나 이름으로 검색한 블록만 읽는다.
- 개념의 소스에는 직접 관리하는 정본과 우선 탐색에 쓰는 참고본을 둔다. 그 밖의 사본은 개념의 `동기화`에 갱신 방법을 기록한다.
- 정본은 사용자가 구체적으로 지정하거나 명시적으로 승인한 범위에서만 변경한다. 그 밖의 변경은 이유·변경 전후·영향을 제안한다. 편집 후 승인 범위와 참조를 확인한다.
- 프로젝트 온톨로지를 설치·구축할 때는 [초기화 절차](references/ontology.md#초기화)를 실행해 프로젝트 루트의 `AGENTS.md`에 정본 링크와 참조 시점을 기록한다. 기존 정본을 연결하는 경우에도 적용한다.
- 온톨로지를 설계·편집·검증할 때 [관리 규칙](references/ontology.md)에서 해당 절을 읽는다.
- 엔티티를 다루기 전에 현재 작업에 필요한 엔티티의 명세만 읽는다. 개념의 `명세문서`를 따르고, 이 키가 없는 기존 정본에서는 `작성규칙문서` 경로를 사용한다. 지정된 경로가 없으면 `docs/ontology/<이름>.md`가 있을 때 읽는다. 명세를 작성·편집할 때는 [엔티티 명세 안내](references/entity-spec.md)를 읽는다.
