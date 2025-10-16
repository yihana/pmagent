import os, json, csv, datetime
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import RetrievalQA
from .prompts import SCOPE_EXTRACT_PROMPT, WBS_SYNTHESIS_PROMPT
from server.core.config import VECTOR_DIR
from server.core.logging import get_logger

log = get_logger("ScopeAgent")

class ScopeAgent:
    def __init__(self, db_path: str = VECTOR_DIR, model: str = "gpt-4o-mini"):
        self.emb = OpenAIEmbeddings()
        self.llm = ChatOpenAI(model=model, temperature=0)
        self.db_path = db_path
        os.makedirs(self.db_path, exist_ok=True)

    def ingest(self, paths, chunk=500, overlap=100):
        docs = []
        for p in paths:
            docs += PyPDFLoader(p).load()
        splits = RecursiveCharacterTextSplitter(chunk_size=chunk, chunk_overlap=overlap).split_documents(docs)
        self.vs = Chroma.from_documents(splits, self.emb, persist_directory=self.db_path)
        self.retriever = self.vs.as_retriever(search_kwargs={"k": 8})
        log.info(f"Ingested {len(splits)} chunks -> {self.db_path}")

    def extract_items(self):
        qa = RetrievalQA.from_chain_type(llm=self.llm, retriever=self.retriever, chain_type="stuff")
        res = qa.run(SCOPE_EXTRACT_PROMPT)
        items = json.loads(res) if isinstance(res, str) else res
        return items

    def synthesize_wbs(self, items, methodology):
        prompt = WBS_SYNTHESIS_PROMPT.format(items=json.dumps(items, ensure_ascii=False), methodology=methodology)
        wbs = self.llm.invoke(prompt).content
        return json.loads(wbs)

    def write_outputs(self, items, wbs, outdir="data/outputs/scope"):
        os.makedirs(outdir, exist_ok=True)
        open(f"{outdir}/scope_statement.md","w",encoding="utf-8").write("# 범위기술서\n\n자동 생성된 초안입니다.\n")
        with open(f"{outdir}/requirements_trace_matrix.csv","w",newline="",encoding="utf-8") as f:
            writer = csv.writer(f); writer.writerow(["REQ_ID","Function","Deliverable"])
            for r in items.get("requirements", []):
                rid = r.get("id") or r.get("name")
                for d in items.get("deliverables",[]):
                    writer.writerow([rid, "TBD", d.get("name")])
        open(f"{outdir}/wbs_structure.json","w",encoding="utf-8").write(json.dumps({"wbs":wbs}, ensure_ascii=False, indent=2))
        os.makedirs(f"{outdir}/logs", exist_ok=True)
        with open(f"{outdir}/logs/execution.jsonl","a",encoding="utf-8") as f:
            f.write(json.dumps({"ts":datetime.datetime.utcnow().isoformat(), "agent":"scope",
                                "outputs":{"scope_statement":"scope_statement.md","rtm":"requirements_trace_matrix.csv","wbs":"wbs_structure.json"}},
                               ensure_ascii=False) + "\n")
        return {
          "scope_statement_md": f"{outdir}/scope_statement.md",
          "rtm_csv": f"{outdir}/requirements_trace_matrix.csv",
          "wbs_json": f"{outdir}/wbs_structure.json"
        }
