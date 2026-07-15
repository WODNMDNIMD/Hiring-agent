from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from recruitflow.ai.resume_parser import parse_resume_with_jd
from recruitflow.core import database as db
from recruitflow.core.workflow import confirm_resume_intake


DEMO_JD = "负责AI Agent招聘运营产品设计，要求3年以上B端产品经验，熟悉SaaS、数据分析、流程自动化。"
DEMO_RESUME = """姓名：李明
电话：13800138000
邮箱：liming@example.com
本科，4年B端产品经验，熟悉SaaS、AI Agent、数据分析和SQL。
最近负责招聘运营自动化项目，完成候选人台账、流程看板和消息通知设计。
期望薪资：20-25K，已离职，可两周内到岗。
"""


if __name__ == "__main__":
    db.init_db()
    job_id = db.add_job("AI产品经理", DEMO_JD, "王芳")
    result = parse_resume_with_jd(DEMO_RESUME, "AI产品经理", DEMO_JD)
    output = confirm_resume_intake(job_id, result, DEMO_RESUME, owner="王芳")
    print(output)
