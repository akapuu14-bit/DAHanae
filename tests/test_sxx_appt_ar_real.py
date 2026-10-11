"""S-xx 黒箱 Phase2 T1 / 層 α-R（AppTest＋実DB 読取のみ）。実DBが使えないときは自動 skip。

対象: S-02, S-07, S-11, S-12, S-13, S-14, S-17, S-18, S-24, S-28, S-32, S-35, S-36, S-37, S-40, S-44, S-58, S-60。
各テストの要件・期待結果は sxx_ar_cases.py の各テストの冒頭コメントと docstring、sxx-phase2-split.md を参照。
実DBには select しか流さない（画面が行う書込は ReadOnlyGuard が握りつぶす）。

実行（god）: python3 -m pytest tests/test_sxx_appt_ar_*.py -v -rs
  - allowed_domains=["*.supabase.co"] が必要。L-A/L-C（偽repo）とは別プロセスで回す。
  - secrets は直下 .streamlit/secrets.toml（worktree からは本体直下も探す）。別の場所は LB_SECRETS=<path>。
"""

from sxx_ar_cases import ArCases
from sxx_real import RealAppCase


class SxxAR(ArCases, RealAppCase):
    pass
