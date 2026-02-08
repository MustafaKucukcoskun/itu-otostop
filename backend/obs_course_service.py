"""
OBS Ders Programı Proxy Servisi

Public OBS API'dan ders bilgilerini çeker, HTML tablosunu parse eder
ve in-memory LRU cache ile hızlı CRN lookup sağlar.

- SearchBransKoduByProgramSeviye → Bölüm listesi (JSON)
- DersProgramSearch → Ders tablosu (HTML → BS4 parse)
- Lazy LRU cache, 1 saat TTL
- Popüler bölümler öncelikli arama
"""

import re
import time
import logging
from typing import Optional
from dataclasses import dataclass, field
from collections import OrderedDict

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

OBS_BASE = "https://obs.itu.edu.tr"
DEPARTMENTS_URL = f"{OBS_BASE}/public/DersProgram/SearchBransKoduByProgramSeviye"
COURSES_URL = f"{OBS_BASE}/public/DersProgram/DersProgramSearch"

# Mühendislik öğrencilerinin %90+'ının ders aldığı bölümler
# CRN lookup'ta önce bunlar aranır → çoğu durumda <5 istek yeter
POPULAR_DEPT_CODES = [
    "MAT", "FIZ", "KIM", "BLG", "EHB", "ELK", "INS", "MAK", "END", "UCK",
    "GEM", "DEN", "CEV", "GID", "JEF", "MET", "KMM", "IBM", "IML", "BIO",
    "HTA", "TEK", "ISL", "KOM", "MAD", "GEO", "AKM", "TUR", "ING", "BED",
    "EUT", "MIM", "PEM", "SBP", "ICM", "MTO", "JEO", "CHZ", "ROS", "UZB",
]

# Day name → index (0=Monday, 4=Friday)
DAY_MAP = {
    "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4,
    "Pazartesi": 0, "Salı": 1, "Çarşamba": 2, "Perşembe": 3, "Cuma": 4,
    "Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4,
    "Pzt": 0, "Sal": 1, "Çar": 2, "Per": 3, "Cum": 4,
}


@dataclass
class CourseSession:
    """Bir dersin bir haftalık oturumu (gün + saat)."""
    day: int            # 0=Pzt, 1=Sal, ..., 4=Cum
    start_time: str     # "08:30"
    end_time: str       # "11:29"
    room: str           # "A11" veya "--"
    building: str       # "MED" veya "--"


@dataclass
class CourseInfo:
    """OBS'den çekilen ders bilgisi."""
    crn: str
    course_code: str
    course_name: str
    instructor: str
    teaching_method: str
    capacity: int
    enrolled: int
    sessions: list[CourseSession] = field(default_factory=list)
    programmes: str = ""


class OBSCourseService:
    """
    OBS Public API proxy.
    
    - Lazy LRU cache (bölüm bazında, TTL ile)
    - Global CRN index (tüm cache'lenen derslerden)
    - Popüler bölümler öncelikli arama
    """

    def __init__(self, cache_ttl: int = 3600, max_cache_depts: int = 50):
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "*/*",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "X-Requested-With": "XMLHttpRequest",
        })
        self.cache_ttl = cache_ttl
        self.max_cache_depts = max_cache_depts

        # Caches
        self._departments: list[dict] | None = None
        self._departments_ts: float = 0
        self._dept_cache: OrderedDict[int, tuple[list[CourseInfo], float]] = OrderedDict()
        self._crn_index: dict[str, CourseInfo] = {}

    # ── Department List ──

    def get_departments(self) -> list[dict]:
        """Bölüm listesini döndürür (1 saat cache)."""
        now = time.time()
        if self._departments and (now - self._departments_ts) < self.cache_ttl:
            return self._departments

        try:
            resp = self.session.get(
                DEPARTMENTS_URL,
                params={"programSeviyeTipiAnahtari": "LS"},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            self._departments = data
            self._departments_ts = now
            logger.info(f"Fetched {len(data)} departments from OBS")
            return data
        except Exception as e:
            logger.error(f"Department fetch failed: {e}")
            return self._departments or []

    # ── Course List by Department ──

    def get_courses(self, brans_kodu_id: int) -> list[CourseInfo]:
        """Bölüme ait dersleri döndürür (cache + parse)."""
        now = time.time()

        # Check cache
        if brans_kodu_id in self._dept_cache:
            courses, ts = self._dept_cache[brans_kodu_id]
            if (now - ts) < self.cache_ttl:
                self._dept_cache.move_to_end(brans_kodu_id)
                return courses

        # Fetch from OBS
        try:
            resp = self.session.get(
                COURSES_URL,
                params={
                    "programSeviyeTipiAnahtari": "LS",
                    "dersBransKoduId": str(brans_kodu_id),
                },
                timeout=15,
            )
            resp.raise_for_status()
            resp.encoding = "utf-8"
            courses = self._parse_courses_html(resp.text)
        except Exception as e:
            logger.error(f"Course fetch failed for dept {brans_kodu_id}: {e}")
            # Return stale cache if available
            if brans_kodu_id in self._dept_cache:
                return self._dept_cache[brans_kodu_id][0]
            return []

        # Update cache
        self._dept_cache[brans_kodu_id] = (courses, now)
        self._dept_cache.move_to_end(brans_kodu_id)

        # Evict oldest entries
        while len(self._dept_cache) > self.max_cache_depts:
            self._dept_cache.popitem(last=False)

        # Update CRN index
        for course in courses:
            self._crn_index[course.crn] = course

        logger.info(f"Cached {len(courses)} courses for dept {brans_kodu_id}")
        return courses

    # ── CRN Lookup ──

    def lookup_crn(self, crn: str) -> Optional[CourseInfo]:
        """
        Tek CRN arama.
        1. Cache index
        2. Popüler bölümler
        3. Tüm bölümler
        """
        # 1. Index check
        if crn in self._crn_index:
            return self._crn_index[crn]

        # Get departments
        departments = self.get_departments()
        if not departments:
            return None

        dept_map = {d["dersBransKodu"]: d["bransKoduId"] for d in departments}

        # 2. Popular departments first
        for code in POPULAR_DEPT_CODES:
            if code in dept_map:
                self.get_courses(dept_map[code])
                if crn in self._crn_index:
                    return self._crn_index[crn]

        # 3. Remaining departments
        searched = {dept_map.get(c) for c in POPULAR_DEPT_CODES if c in dept_map}
        for dept in departments:
            dept_id = dept["bransKoduId"]
            if dept_id in searched:
                continue
            self.get_courses(dept_id)
            if crn in self._crn_index:
                return self._crn_index[crn]

        return None

    def lookup_crns(self, crns: list[str]) -> dict[str, Optional[CourseInfo]]:
        """Toplu CRN arama (batch — daha verimli)."""
        results: dict[str, Optional[CourseInfo]] = {}
        missing: list[str] = []

        # Check cache first
        for crn in crns:
            if crn in self._crn_index:
                results[crn] = self._crn_index[crn]
            else:
                missing.append(crn)

        if not missing:
            return results

        # Get departments
        departments = self.get_departments()
        if not departments:
            for crn in missing:
                results[crn] = None
            return results

        dept_map = {d["dersBransKodu"]: d["bransKoduId"] for d in departments}
        remaining = set(missing)

        # Popular departments first
        for code in POPULAR_DEPT_CODES:
            if not remaining:
                break
            if code in dept_map:
                self.get_courses(dept_map[code])
                found = remaining & set(self._crn_index.keys())
                for crn in found:
                    results[crn] = self._crn_index[crn]
                remaining -= found

        # Remaining departments
        if remaining:
            searched = {dept_map.get(c) for c in POPULAR_DEPT_CODES if c in dept_map}
            for dept in departments:
                if not remaining:
                    break
                dept_id = dept["bransKoduId"]
                if dept_id in searched:
                    continue
                self.get_courses(dept_id)
                found = remaining & set(self._crn_index.keys())
                for crn in found:
                    results[crn] = self._crn_index[crn]
                remaining -= found

        # Mark unfound
        for crn in missing:
            if crn not in results:
                results[crn] = None

        return results

    # ── HTML Parser ──

    def _parse_courses_html(self, html: str) -> list[CourseInfo]:
        """OBS DersProgramSearch HTML tablosunu parse eder."""
        soup = BeautifulSoup(html, "html.parser")
        courses: list[CourseInfo] = []

        table = soup.find("table")
        if not table:
            logger.warning("No table found in OBS HTML response")
            return courses

        rows = table.find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 10:
                continue

            texts = [c.get_text(strip=True) for c in cols]

            # CRN sütununu bul (5 haneli sayı)
            crn_idx = None
            for i, text in enumerate(texts):
                if re.match(r"^\d{5}$", text):
                    crn_idx = i
                    break

            if crn_idx is None:
                continue

            try:
                crn = texts[crn_idx]
                course_code = texts[crn_idx + 1] if crn_idx + 1 < len(texts) else ""
                course_name = texts[crn_idx + 2] if crn_idx + 2 < len(texts) else ""
                teaching_method = texts[crn_idx + 3] if crn_idx + 3 < len(texts) else ""
                instructor = texts[crn_idx + 4] if crn_idx + 4 < len(texts) else ""
                building_str = texts[crn_idx + 5] if crn_idx + 5 < len(texts) else ""
                days_str = texts[crn_idx + 6] if crn_idx + 6 < len(texts) else ""
                times_str = texts[crn_idx + 7] if crn_idx + 7 < len(texts) else ""
                rooms_str = texts[crn_idx + 8] if crn_idx + 8 < len(texts) else ""
                capacity_str = texts[crn_idx + 9] if crn_idx + 9 < len(texts) else "0"
                enrolled_str = texts[crn_idx + 10] if crn_idx + 10 < len(texts) else "0"

                # Programmes sütununu bul (_LS pattern)
                programmes = ""
                for i in range(crn_idx + 11, min(crn_idx + 15, len(texts))):
                    if "_LS" in texts[i] or "_YD" in texts[i]:
                        programmes = texts[i]
                        break

                capacity = int(capacity_str) if capacity_str.isdigit() else 0
                enrolled = int(enrolled_str) if enrolled_str.isdigit() else 0

                sessions = self._parse_sessions(days_str, times_str, rooms_str, building_str)

                courses.append(CourseInfo(
                    crn=crn,
                    course_code=course_code,
                    course_name=course_name,
                    instructor=instructor,
                    teaching_method=teaching_method,
                    capacity=capacity,
                    enrolled=enrolled,
                    sessions=sessions,
                    programmes=programmes,
                ))
            except (IndexError, ValueError) as e:
                logger.debug(f"Failed to parse row: {e}")
                continue

        return courses

    def _parse_sessions(
        self, days_str: str, times_str: str, rooms_str: str, building_str: str,
    ) -> list[CourseSession]:
        """Gün/saat/salon string'lerini session listesine çevirir."""
        sessions: list[CourseSession] = []

        days = days_str.split()
        times = re.findall(r"(\d{2}:\d{2})/(\d{2}:\d{2})", times_str)
        rooms = rooms_str.split() if rooms_str else []
        buildings = building_str.split() if building_str else []

        for i, day_name in enumerate(days):
            day_idx = DAY_MAP.get(day_name)
            if day_idx is None:
                continue

            if i < len(times):
                start_time, end_time = times[i]
            else:
                continue

            room = rooms[i] if i < len(rooms) else "--"
            building = buildings[i] if i < len(buildings) else "--"

            sessions.append(CourseSession(
                day=day_idx,
                start_time=start_time,
                end_time=end_time,
                room=room,
                building=building,
            ))

        return sessions


# ── Singleton ──

_service: Optional[OBSCourseService] = None


def get_obs_service() -> OBSCourseService:
    """Global singleton instance."""
    global _service
    if _service is None:
        _service = OBSCourseService()
    return _service
