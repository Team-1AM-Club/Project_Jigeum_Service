"""해석 서비스 (Interpret Service).

자연어 입력 → TripDraft 변환 + 확인 질문 생성을 담당한다.
모델 제공자(자연어 해석)를 호출하여 수행한다.

T036: interpret_service.py 생성.
"""

import logging
from typing import Optional, List
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.schemas.mobility import (
    TripDraft,
    ConfirmationQuestion,
    InterpretRequest,
    InterpretResponse,
    PlaceInfo,
)
from app.services.provider_interfaces import ModelProvider, ProviderResult

logger = logging.getLogger(__name__)
SEOUL_TZ = ZoneInfo("Asia/Seoul")


class InterpretService:
    """자연어 해석 서비스.

    사용자의 자연어 입력을 받아 TripDraft로 변환하고,
    확인이 필요한 항목(장소 등)에 대한 확인 질문을 생성한다.
    """

    def __init__(self, model_provider: ModelProvider):
        """초기화.

        Args:
            model_provider: 자연어 해석을 수행할 모델 제공자.
        """
        self.model_provider = model_provider

    async def interpret(
        self,
        request: InterpretRequest,
    ) -> InterpretResponse:
        """자연어 입력 해석.

        Args:
            request: InterpretRequest (natural_language, conversation_id)

        Returns:
            InterpretResponse: TripDraft + 확인 질문 목록
        """
        natural_lang = request.natural_language.strip()

        if not natural_lang:
            raise ValueError("자연어 입력이 비어있습니다.")

        # 모델 제공자 호출하여 TripDraft 생성
        parsed = await self._parse_natural_language(natural_lang)

        # 확인 질문 생성
        questions = self._generate_confirmation_questions(parsed)

        # TripDraft 구성
        trip_draft = TripDraft(
            origin_place_id=parsed.get("origin_place_id"),
            origin_place_name=parsed.get("origin_place_name"),
            destination_place_id=parsed.get("destination_place_id"),
            destination_place_name=parsed.get("destination_place_name"),
            departure_at=parsed.get("departure_at"),
            arrival_deadline=parsed.get("arrival_deadline"),
            arrival_preference_minutes=parsed.get("arrival_preference_minutes", 10),
            transport_mode=parsed.get("transport_mode"),
            natural_language=natural_lang,
        )

        requires_confirmation = any(
            q.question_type == "place_confirmation" for q in questions
        ) or not parsed.get("origin_place_id") or not parsed.get("destination_place_id")

        return InterpretResponse(
            trip_draft=trip_draft,
            confirmation_questions=questions,
            requires_confirmation=requires_confirmation,
            next_action="confirm" if requires_confirmation else "plan",
        )

    async def _parse_natural_language(self, text: str) -> dict:
        """자연어를 파싱하여 TripDraft 구성 요소 반환.

        모델 제공자(LLM)를 호출하여 자연어를 해석한다.
        실패 시 Mock/fallback 로직으로 기본 해석 수행.

        Args:
            text: 사용자 자연어 입력

        Returns:
            dict: origin_place_id, destination_place_id, arrival_deadline,
                  arrival_preference_minutes, transport_mode 등
        """
        # 모델 제공자 호출 시도
        model_result = await self.model_provider.interpret(
            user_text=text,
            context={"task": "trip_interpretation"},
        )

        if model_result.ok and model_result.data:
            # 제공자 결과를 파싱하여 반환
            return self._normalize_parsed_result(model_result.data)

        # 제공자 실패 → fallback: 규칙 기반 기본 해석
        logger.warning("모델 제공자 실패, fallback 규칙 기반 해석 사용")
        # provider에서 파싱된 deadline이 있으면 fallback에 전달
        fallback_deadline = None
        if model_result.ok and model_result.data:
            normalized = self._normalize_parsed_result(model_result.data)
            fallback_deadline = normalized.get("arrival_deadline")
        return self._fallback_parse(text, existing_deadline=fallback_deadline)

    def _normalize_parsed_result(self, data: dict) -> dict:
        """모델 제공자 결과를 정규화하여 표준 형식으로 변환.

        MockModelProvider와 실제 LLM 제공자 양쪽의 응답 형식을 처리한다.
        - MockProvider: origin_place_id, destination_place_id, arrival_deadline(문자열),
                        transport_mode, departure_time, needs_confirmation
        - LLM 제공자: 더 풍부한 필드 (place_name, arrival_preference_minutes 등)
        """
        # 기본 필드 추출 (두 제공자 공통)
        result = {
            "origin_place_id": data.get("origin_place_id"),
            "origin_place_name": data.get("origin_place_name"),
            "destination_place_id": data.get("destination_place_id"),
            "destination_place_name": data.get("destination_place_name"),
            "departure_at": data.get("departure_at") or data.get("departure_time"),
            "arrival_deadline": data.get("arrival_deadline"),
            "arrival_preference_minutes": data.get("arrival_preference_minutes", 10),
            "transport_mode": data.get("transport_mode"),
        }

        # MockProvider: arrival_deadline이 "2026-09-16T10:00:00+09:00" 문자열 → datetime으로
        # (도착 마감 설정이 ingress에서 제대로 파싱되지 않은 경우 처리)
        dl = result.get("arrival_deadline")
        if isinstance(dl, str):
            try:
                result["arrival_deadline"] = datetime.fromisoformat(dl)
            except (ValueError, TypeError):
                result["arrival_deadline"] = None

        # departure_at도 문자열일 수 있음
        dep = result.get("departure_at")
        if isinstance(dep, str):
            try:
                result["departure_at"] = datetime.fromisoformat(dep)
            except (ValueError, TypeError):
                result["departure_at"] = None

        # arrival_preference_minutes 검증
        pref = result.get("arrival_preference_minutes")
        if pref is None or not isinstance(pref, int):
            result["arrival_preference_minutes"] = 10
        else:
            result["arrival_preference_minutes"] = max(0, min(60, pref))

        # transport_mode 검증
        mode = result.get("transport_mode")
        if mode and mode not in ("subway", "bus", "walking", "taxi", "bicycle"):
            result["transport_mode"] = None

        # MockProvider가 needs_confirmation을 제공한 경우, place_name이 없으면 생성
        if data.get("needs_confirmation") and not result.get("origin_place_name") and result.get("origin_place_id"):
            result["origin_place_name"] = result["origin_place_id"].replace("place_", "").replace("_", " ")
        if data.get("needs_confirmation") and not result.get("destination_place_name") and result.get("destination_place_id"):
            result["destination_place_name"] = result["destination_place_id"].replace("place_", "").replace("_", " ")

        return result

    def _fallback_parse(self, text: str, existing_deadline: Optional[datetime] = None) -> dict:
        """규칙 기반 fallback 파싱.

        모델 제공자 실패 시 기본적인 시간/장소 패턴 매칭으로 해석.
        existing_deadline이 있으면 그것을 유지 (제공자에서 파싱한 값).
        """
        import re

        result = {
            "origin_place_id": None,
            "origin_place_name": None,
            "destination_place_id": None,
            "destination_place_name": None,
            "departure_at": None,
            "arrival_deadline": existing_deadline,  # 제공자에서 파싱한 값 우선
            "arrival_preference_minutes": 10,
            "transport_mode": None,
        }

        # fallback에서는 기존 deadline이 없으면 시간 패턴 추출
        if existing_deadline is None:
            now = datetime.now(SEOUL_TZ)

            # 시간 패턴 추출: "오후 7시", "7pm", "19:00", "7시"
            time_patterns = [
                r'(\d{1,2})\s*:\s*(\d{2})\s*(?:까지|에|까지\s*도착)',
                r'오후\s*(\d{1,2})\s*시',
                r'저녁\s*(\d{1,2})\s*시',
                r'(\d{1,2})\s*pm',
                r'(\d{1,2})\s*시\s*까지',
                r'(\d{1,2})\s*시\s*에\s*도착',
            ]

            arrival_time = None
            for pattern in time_patterns:
                m = re.search(pattern, text)
                if m:
                    if len(m.groups()) >= 2 and ':' in text[m.start():m.end()]:
                        hour, minute = int(m.group(1)), int(m.group(2))
                    elif len(m.groups()) >= 1:
                        hour = int(m.group(1))
                        minute = 0
                        # 오후/저녁 보정
                        if '오후' in text[:m.start()] or '저녁' in text[:m.start()] or 'pm' in text[m.start():m.end()].lower():
                            if hour < 12:
                                hour += 12
                    else:
                        continue

                    if 0 <= hour <= 23 and 0 <= minute <= 59:
                        arrival_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                        # 오늘 날짜 기준, 과거면 내일
                        if arrival_time < now:
                            arrival_time += timedelta(days=1)
                        break

            if arrival_time:
                result["arrival_deadline"] = arrival_time

        # 장소 힌트: "~역에서", "~에 도착", "집에서" 등
        if '집' in text or 'home' in text.lower():
            result["origin_place_name"] = "집"
            result["origin_place_id"] = None  # 집은 장소 ID 미확정

        # 목적지 패턴: "~역에", "~에 도착해야"
        dest_patterns = [
            (r'(\w+)\s*역에\s*(?:도착|가야|가야\s*해)', 'subway_station'),
            (r'(\w+)\s*터미널', 'terminal'),
            (r'(\w+)\s*병원', 'hospital'),
            (r'(\w+)\s*회사', 'office'),
            (r'(\w+)\s*학교', 'school'),
        ]

        for pattern, place_type in dest_patterns:
            m = re.search(pattern, text)
            if m:
                place_name = m.group(1)
                result["destination_place_name"] = place_name
                result["destination_place_id"] = None  # 실제 ID 확인 필요
                break

        return result
    def _generate_confirmation_questions(self, parsed: dict) -> List[ConfirmationQuestion]:
        """해석 결과로부터 확인 질문 생성.

        Args:
            parsed: _parse_natural_language / _normalize_parsed_result 결과

        Returns:
            List[ConfirmationQuestion]: 확인 질문 목록
        """
        questions = []

        # 출발지 확인 질문
        origin_id = parsed.get("origin_place_id")
        origin_name = parsed.get("origin_place_name")
        if not origin_id and not origin_name:
            questions.append(ConfirmationQuestion(
                question_type="place_confirmation",
                place_id=None,
                place_name="출발지",
                question="출발지를 확인해주세요. '집'에서 출발하시나요?",
                alternatives=[
                    {"place_id": None, "place_name": "집", "description": "현재 위치/집"},
                    {"place_id": None, "place_name": "다른 장소", "description": "직접 입력"},
                ],
            ))
        elif origin_id is None and origin_name:
            # 이름은 있지만 ID 미확정
            questions.append(ConfirmationQuestion(
                question_type="place_confirmation",
                place_id=None,
                place_name=origin_name,
                question=f"출발지를 '{origin_name}'로 확인하셨나요?",
                alternatives=[],
            ))
        elif origin_id:
            # ID는 있지만 확인 질문 포함 (place_id 포함)
            questions.append(ConfirmationQuestion(
                question_type="place_confirmation",
                place_id=origin_id,
                place_name=origin_name or origin_id.replace("place_", "").replace("_", " "),
                question=f"출발지를 '{origin_name or origin_id}'로 확인하셨나요?",
                alternatives=[],
            ))

        # 목적지 확인 질문
        dest_id = parsed.get("destination_place_id")
        dest_name = parsed.get("destination_place_name")
        if not dest_id and not dest_name:
            questions.append(ConfirmationQuestion(
                question_type="place_confirmation",
                place_id=None,
                place_name="목적지",
                question="목적지를 확인해주세요. 어디로 가시나요?",
                alternatives=[],
            ))
        elif dest_id is None and dest_name:
            questions.append(ConfirmationQuestion(
                question_type="place_confirmation",
                place_id=None,
                place_name=dest_name,
                question=f"목적지를 '{dest_name}'로 확인하셨나요?",
                alternatives=[],
            ))
        elif dest_id:
            questions.append(ConfirmationQuestion(
                question_type="place_confirmation",
                place_id=dest_id,
                place_name=dest_name or dest_id.replace("place_", "").replace("_", " "),
                question=f"목적지를 '{dest_name or dest_id}'로 확인하셨나요?",
                alternatives=[],
            ))

        # 도착 마감 시간 확인
        if parsed.get("arrival_deadline"):
            deadline = parsed["arrival_deadline"]
            time_str = deadline.strftime("%H시 %M분")
            questions.append(ConfirmationQuestion(
                question_type="condition_confirmation",
                place_id=None,
                place_name=None,
                question=f"도착 마감 시각을 '{time_str}'으로 확인하셨나요?",
                alternatives=[],
            ))
        else:
            questions.append(ConfirmationQuestion(
                question_type="condition_confirmation",
                place_id=None,
                place_name=None,
                question="도착 마감 시각을 알려주세요. 몇시까지 도착해야 하나요?",
                alternatives=[],
            ))

        # 이동수단 확인
        if parsed.get("transport_mode"):
            mode = parsed["transport_mode"]
            questions.append(ConfirmationQuestion(
                question_type="condition_confirmation",
                place_id=None,
                place_name=None,
                question=f"이동수단을 '{mode}'로 확인하셨나요?",
                alternatives=[],
            ))

        # 도착 여유 시간 확인
        pref = parsed.get("arrival_preference_minutes", 10)
        questions.append(ConfirmationQuestion(
            question_type="condition_confirmation",
            place_id=None,
            place_name=None,
            question=f"도착 여유 시간을 {pref}분으로 확인하셨나요? (여유 시간: 도착 마감 전 미리 도착하기 위한 버퍼)",
            alternatives=[],
        ))

        return questions
