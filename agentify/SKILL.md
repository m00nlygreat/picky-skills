---
name: agentify
description: Initialize, connect, and maintain an agent workspace with AGENTS.md, SOUL.md, MEMORY.md, HEARTBEAT.md, and indexed long-term memory. Use for agent workspace setup, memory maintenance, or heartbeat checks and scheduling.
---

# Agentify

## 초기화와 연결

사용자가 지정한 작업공간을 사용한다. 경로를 지정하지 않았다면 현재 프로젝트 루트를 사용하고, Git 저장소 밖에서는 현재 작업 디렉터리를 사용한다. 초기화 또는 연결 복구를 요청받으면 이 스킬 디렉터리 기준으로 다음 도우미를 실행한다.

```text
python <스킬 디렉터리>/scripts/init_agentify.py --project-root <작업공간>
```

도우미가 출력한 실제 지침 파일을 읽고 생성된 문서 링크를 확인한다. 기존 문서는 현재 내용을 기준으로 사용한다. 기존 기억을 처음 연결할 때는 실제 문서를 확인해 필요한 항목을 `memory/INDEX.md`에 추가한다. 지침과 충돌하는 기존 설정이 발견되면 그 차이를 알려 해소한다.

## 일상 운영

[AGENTS.md에 추가하는 지침](assets/AGENTS.section.md)에 따라 문서를 읽고 갱신한다. 대상 작업공간에 이미 연결한 지침과 설정을 기준으로 작업한다. 기억의 수정과 정리를 요청받으면 관련 항목과 근거를 먼저 읽고, 변경한 기록과 인덱스 링크가 일치하는지 확인한다. 사용자가 기억하거나 정정하라고 요청한 정보는 작업 종료까지 미루지 않고 반영한다.

[HEARTBEAT.md 템플릿](assets/HEARTBEAT.md)은 세션 점검의 기본 형식을 보여 준다. 설정된 점검을 실행하고, 직접 점검 요청에는 실제 확인 결과를 간단히 답한다. 완료할 수 없었던 점검은 마지막 성공 시각을 갱신하지 않는다.

## 예약 등록

주기 점검을 설정할 때 작업공간에 접근 가능한 하네스 내장 스케줄러가 있는지 확인한다. 사용자가 예약을 요청하면 점검 대상, 주기, 시간대를 확인한다. 사용자가 주기 점검만 설정했고 예약이 적합하면 등록 여부를 명시적으로 물어본다. 사용자가 요청 또는 동의한 범위에서만 등록하거나 수정한다. 스케줄러를 쓸 수 없으면 세션 점검을 적용한다.

등록 전에 저장된 예약 ID나 작업공간 경로로 기존 예약을 확인한다. 결과가 불확실하면 재시도 전에 예약을 다시 조회한다. 등록이 확인되면 식별자와 실행 주기를 `HEARTBEAT.md`에 기록한다. 예약의 실행 지침에는 대상 작업공간을 지정하고, 실행마다 현재 `AGENTS.md`와 `HEARTBEAT.md`를 읽어 기한이 된 점검을 수행하도록 적는다.
