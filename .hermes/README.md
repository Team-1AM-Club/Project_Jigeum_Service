# 프로젝트 Hermes 자산

이 디렉토리는 개인 Hermes 홈이 아니다. `config.yaml`, `.env`, 세션·메모리·로그 등 개인 상태는 각자의 Hermes 홈에서 관리하고 커밋하지 않는다.

`skills/<name>/`에 팀이 보유한 실제 Skill 원본을 가져온다. 현재 `.gitkeep`만 있는 폴더는 설치되거나 실행 가능한 Skill이 아니다. 원본을 가져올 때 `SKILL.md`와 필요한 `references/`, `scripts/`를 함께 검증한다. 생성 프롬프트를 검증된 구현 파일로 간주하지 않는다.

Skill은 Agent별로 복제하지 않는다. 여러 SubAgent가 같은 원본을 사용할 수 있다. backend의 로더·도구 연결과 컨테이너에 Skill을 포함하는 절차는 별도 구현 대상이다.

현재 공식 문서상 Git 프로젝트의 `.hermes/skills/`를 탐색하며, 내용을 검토한 뒤 저장소 안에서 `hermes skills trust`로 신뢰를 승인할 수 있다. 설치된 버전이 이 기능을 지원하는지 확인한다. 이 저장소는 신뢰 설정을 자동 변경하지 않는다.

- [프로젝트 Skill 문서](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills#project-local-skills)
- [Skill 구조](https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills)
