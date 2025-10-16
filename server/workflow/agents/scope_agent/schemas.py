from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class DocumentRef(BaseModel):
    path: str
    type: str = 'RFP'

class ScopeInput(BaseModel):
    project_name: str
    methodology: str
    documents: List[DocumentRef]
    options: Optional[Dict[str, Any]] = None

class ScopeOutput(BaseModel):
    scope_statement_md: str
    rtm_csv: str
    wbs_json: str
