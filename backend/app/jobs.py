"""배치 명령 진입점.

근거: JSD-DOM-002 1장, 4.15, JSD-MS-015
사용법: python -m app.jobs <명령>
명령: purge, refresh_defaulters, load_region_codes, warm_samples, usage_report
"""

import argparse
import asyncio
import sys


async def cmd_purge() -> None:
    print("[jobs] purge executed")


async def cmd_refresh_defaulters() -> None:
    print("[jobs] refresh_defaulters executed")


async def cmd_load_region_codes(file_path: str) -> None:
    print(f"[jobs] load_region_codes executed with {file_path}")


async def cmd_warm_samples() -> None:
    print("[jobs] warm_samples executed")


async def cmd_usage_report() -> None:
    print("[jobs] usage_report executed")


def main() -> None:
    parser = argparse.ArgumentParser(description="보증금지킴 배치 작업 러너")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("purge", help="만료 데이터 정리")
    subparsers.add_parser("refresh_defaulters", help="HUG 상습 채무불이행자 명단 갱신")

    parser_load = subparsers.add_parser("load_region_codes", help="법정동코드 CSV 적재")
    parser_load.add_argument("file", help="법정동코드 CSV 파일 경로")

    subparsers.add_parser("warm_samples", help="예시 등기부 파싱 캐시 웜업")
    subparsers.add_parser("usage_report", help="일일 비용 및 사용량 점검")

    args = parser.parse_args()

    if args.command == "purge":
        asyncio.run(cmd_purge())
    elif args.command == "refresh_defaulters":
        asyncio.run(cmd_refresh_defaulters())
    elif args.command == "load_region_codes":
        asyncio.run(cmd_load_region_codes(args.file))
    elif args.command == "warm_samples":
        asyncio.run(cmd_warm_samples())
    elif args.command == "usage_report":
        asyncio.run(cmd_usage_report())


if __name__ == "__main__":
    main()
