"""检索基准测试：对比纯向量 vs 混合检索的召回率。

用法：
    python -m pytest tests/test_retrieval_benchmark.py -v -s

或独立运行：
    python tests/test_retrieval_benchmark.py
"""
import logging
import time
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("benchmark")


# ── 测试数据集（模拟真实文档） ──
SAMPLE_DOCS = [
    {
        "name": "2024年度工作总结报告.txt",
        "category": "work_doc",
        "text": """
        2024年度工作总结报告

        一、工作概述
        本年度主要负责公司核心业务系统的开发与维护，参与了三个重要项目的交付工作。
        全年累计完成需求开发120项，修复bug 80余个，代码review 200余次。

        二、核心成果
        1. 完成了订单管理系统的重构，性能提升40%
        2. 主导了微服务架构迁移，系统可用性达到99.9%
        3. 建立了完善的监控告警体系，故障响应时间缩短60%

       三、团队协作
        作为技术组长，带领5人团队完成了多个跨部门协作项目。
        组织了12次技术分享会，提升了团队整体技术水平。

       四、个人成长
        学习了云原生相关技术，获得了AWS认证。
        参与了公司内部讲师培训，提升了沟通表达能力。

       五、2025年规划
        计划深入研究AI大模型应用，探索LLM在企业场景的落地。
        持续优化系统架构，提升团队研发效率。
        """,
    },
    {
        "name": "Q3财务报表.xlsx",
        "category": "bill",
        "text": """
        第三季度财务报表

        收入明细：
        主营业务收入：1,200,000元
        其他业务收入：150,000元
        投资收益：30,000元
        总收入：1,380,000元

        支出明细：
        人员工资：600,000元
        办公租金：120,000元
        服务器费用：80,000元
        市场推广：200,000元
        其他支出：50,000元
        总支出：1,050,000元

        净利润：330,000元
        利润率：23.9%

        应收账款：200,000元
        应付账款：150,000元
        现金流：健康
        """,
    },
    {
        "name": "劳动合同范本.docx",
        "category": "contract",
        "text": """
        劳动合同

        甲方（用人单位）：XX科技有限公司
       法定代表人：张三
        地址：北京市朝阳区科技园区

        乙方（劳动者）：李四
        身份证号：110105199001011234

        第一条 合同期限
        本合同为固定期限劳动合同，自2024年1月1日起至2026年12月31日止。

        第二条 工作内容
        乙方同意根据甲方工作需要，担任软件工程师岗位。

        第三条 劳动报酬
        乙方月工资为人民币25000元，甲方每月15日前支付上月工资。

        第四条 社会保险
        甲方按国家规定为乙方缴纳养老保险、医疗保险、失业保险、工伤保险、生育保险。

        第五条 劳动保护
        甲方为乙方提供符合国家规定的劳动安全卫生条件和必要的劳动防护用品。
        """,
    },
    {
        "name": "会议纪要_20241215.md",
        "category": "note",
        "text": """
        # 技术评审会议纪要

        **会议时间**：2024年12月15日 14:00-16:00
        **参会人员**：张三、李四、王五、赵六
        **会议地点**：3号会议室

        ## 议题一：系统架构升级方案

        讨论了当前单体架构面临的性能瓶颈，决定采用微服务架构进行重构。

        关键决策：
        1. 使用Kubernetes作为容器编排平台
        2. 采用gRPC作为服务间通信协议
        3. 数据库按业务拆分，减少耦合

        ## 议题二：技术选型

        经过讨论，确定以下技术栈：
        - 后端：Python FastAPI + LangGraph
        - 前端：React + Vite
        - 数据库：PostgreSQL + Chroma向量库
        - 部署：Docker + K8s

        ## 下一步行动
        - 张三：完成架构设计文档（12月20日前）
        - 李四：搭建开发环境（12月18日前）
        - 王五：调研Chroma性能（12月22日前）
        """,
    },
    {
        "name": "报销制度说明.pdf",
        "category": "contract",
        "text": """
        公司费用报销管理制度

        一、报销范围
        1. 差旅交通费：机票、火车票、出租车费
        2. 餐饮补助：出差期间餐饮费用，每日限额200元
        3. 住宿费用：出差住宿，一线城市限额500元/晚
        4. 办公用品：文具、打印耗材等
        5. 培训费用：与工作相关的培训

        二、报销流程
        1. 员工填写报销单，附上发票原件
        2. 部门经理审批
        3. 财务审核票据合规性
        4. 出纳付款

        三、注意事项
        - 发票必须为增值税专用发票或普通发票
        - 报销时限：费用发生后30天内
        - 单笔超过5000元需总经理审批
        - 餐饮发票需注明用餐人员名单
        """,
    },
]


# ── 测试查询（query → 期望命中的文档索引） ──
TEST_QUERIES = [
    {
        "query": "年度工作总结",
        "expected": [0],
        "desc": "精确语义匹配",
    },
    {
        "query": "工资收入支出",
        "expected": [1],
        "desc": "财务关键词",
    },
    {
        "query": "劳动合同社保",
        "expected": [2],
        "desc": "合同条款检索",
    },
    {
        "query": "会议决策架构升级",
        "expected": [3],
        "desc": "会议纪要匹配",
    },
    {
        "query": "报销流程发票",
        "expected": [4],
        "desc": "制度文档检索",
    },
    {
        "query": "周报",  # 同义词扩展测试：周报 → 周总结/本周工作
        "expected": [0],
        "desc": "同义词扩展（周报→总结）",
    },
    {
        "query": "K8s部署",
        "expected": [3],
        "desc": "技术术语精确匹配",
    },
    {
        "query": "出差餐饮费用限额",
        "expected": [4],
        "desc": "多关键词组合",
    },
]


def _setup_test_data():
    """将测试文档写入知识库。"""
    from memory_store.chroma_kb import add_document
    from memory_store.bm25_index import build_index

    logger.info("═══ 写入测试数据 ═══")
    for doc in SAMPLE_DOCS:
        result = add_document(
            file_path=f"/test/{doc['name']}",
            text=doc["text"],
            category=doc["category"],
            file_name=doc["name"],
        )
        logger.info("  %s → %s (%d chunks)", doc["name"], result.get("status"), result.get("chunks", 0))

    # 重建 BM25 索引
    build_index()


def _evaluate_recall(results: list[dict], expected_indices: list[int], top_k: int = 3) -> bool:
    """检查 top_k 结果中是否包含期望文档。"""
    for r in results[:top_k]:
        fp = r.get("file_path", "")
        for idx in expected_indices:
            if f"/test/{SAMPLE_DOCS[idx]['name']}" in fp:
                return True
    return False


def run_benchmark() -> dict[str, Any]:
    """运行检索基准测试。"""
    from memory_store.chroma_kb import search as vec_search
    from memory_store.bm25_index import hybrid_search, search_bm25

    _setup_test_data()

    logger.info("\n═══ 开始检索基准测试 ═══\n")

    vec_hits = 0
    bm25_hits = 0
    hybrid_hits = 0
    total = len(TEST_QUERIES)

    for i, q in enumerate(TEST_QUERIES, 1):
        query = q["query"]
        expected = q["expected"]
        desc = q["desc"]

        logger.info("[%d/%d] 查询: \"%s\" (%s)", i, total, query, desc)

        # 纯向量检索
        vec_results = vec_search(query, top_k=3, hybrid=False)
        vec_hit = _evaluate_recall(vec_results, expected)
        vec_hits += vec_hit

        # 纯 BM25 检索
        bm25_results = search_bm25(query, top_k=3)
        bm25_hit = _evaluate_recall(bm25_results, expected)
        bm25_hits += bm25_hit

        # 混合检索
        hybrid_results = hybrid_search(query, top_k=3)
        hybrid_hit = _evaluate_recall(hybrid_results, expected)
        hybrid_hits += hybrid_hit

        logger.info("  向量: %s | BM25: %s | 混合: %s",
                     "✓" if vec_hit else "✗",
                     "✓" if bm25_hit else "✗",
                     "✓" if hybrid_hit else "✗")

    # 汇总
    vec_recall = vec_hits / total * 100
    bm25_recall = bm25_hits / total * 100
    hybrid_recall = hybrid_hits / total * 100
    improvement = hybrid_recall - vec_recall

    logger.info("\n═══ 测试结果 ═══")
    logger.info("纯向量召回率: %.1f%% (%d/%d)", vec_recall, vec_hits, total)
    logger.info("纯BM25召回率: %.1f%% (%d/%d)", bm25_recall, bm25_hits, total)
    logger.info("混合检索召回率: %.1f%% (%d/%d)", hybrid_recall, hybrid_hits, total)
    logger.info("混合 vs 向量提升: %+.1f%%", improvement)

    return {
        "vector_recall": vec_recall,
        "bm25_recall": bm25_recall,
        "hybrid_recall": hybrid_recall,
        "improvement": improvement,
    }


if __name__ == "__main__":
    results = run_benchmark()
    print(f"\n最终结论: 混合检索较纯向量召回率提升 {results['improvement']:+.1f}%")
