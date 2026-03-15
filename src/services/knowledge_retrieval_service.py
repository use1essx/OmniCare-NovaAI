from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from src.database.models_questionnaire import QuestionnaireQuestion, QuestionnaireBank
from src.database.models_knowledge_base import QuestionBankItem
from src.database.vector_store import get_vector_store
from src.core.logging import get_logger

logger = get_logger(__name__)

class KnowledgeRetrievalService:
    """
    Service to retrieve relevant questions and knowledge for the chat agent.
    """
    
    def __init__(self, db: Session = None):
        self.db = db
        self.vector_store = get_vector_store()
        
    @contextmanager
    def _get_session(self):
        """Helper to get DB session context"""
        if self.db:
            yield self.db
        else:
            from src.database.connection import get_sync_session
            with get_sync_session() as session:
                yield session

    def retrieve_relevant_questions(self, topic: str, age_group: str = None, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieve relevant assessment questions based on topic and age group.
        """
        try:
            with self._get_session() as session:
                # 1. Search in QuestionnaireQuestion (Structured Questionnaires)
                query = session.query(QuestionnaireQuestion).join(QuestionnaireBank)
                
                # Filter by topic/category
                if topic:
                    topic_term = f"%{topic}%"
                    query = query.filter(
                        or_(
                            QuestionnaireQuestion.category.ilike(topic_term),
                            QuestionnaireQuestion.question_text.ilike(topic_term),
                            QuestionnaireBank.title.ilike(topic_term)
                        )
                    )
                
                # Filter by age group if provided
                if age_group:
                    if age_group == "child":
                        query = query.filter(QuestionnaireBank.target_age_max <= 12)
                    elif age_group == "teen":
                        query = query.filter(QuestionnaireBank.target_age_min >= 13)
                
                # Get random questions to avoid repetition
                questions = query.order_by(func.random()).limit(limit).all()
                
                results = []
                for q in questions:
                    results.append({
                        "id": q.id,
                        "text": q.question_text_zh or q.question_text,
                        "type": "questionnaire",
                        "category": q.category
                    })
                    
                # 2. Search in QuestionBankItem (Knowledge Base Questions)
                kb_query = session.query(QuestionBankItem)
                if topic:
                    kb_query = kb_query.filter(
                        or_(
                            QuestionBankItem.category.ilike(f"%{topic}%"),
                            QuestionBankItem.question_text.ilike(f"%{topic}%")
                        )
                    )
                    
                kb_questions = kb_query.order_by(func.random()).limit(limit).all()
                
                for q in kb_questions:
                    results.append({
                        "id": q.id,
                        "text": q.question_text,
                        "type": "knowledge_base",
                        "category": q.category
                    })
                    
                return results[:limit]
            
        except Exception as e:
            logger.error(f"Error retrieving questions: {e}")
            return []

    def retrieve_knowledge(self, query_text: str, limit: int = 2) -> List[str]:
        """
        Retrieve relevant knowledge chunks using vector search.
        """
        try:
            results = self.vector_store.search(query=query_text, n_results=limit)
            
            documents = results.get('documents', [])
            if not documents:
                return []
                
            # If documents is a list of lists (common in some Chroma versions), flatten it
            if documents and isinstance(documents[0], list):
                documents = [doc for sublist in documents for doc in sublist]
                
            return documents[:limit]
            
        except Exception as e:
            logger.error(f"Error retrieving knowledge: {e}")
            return []
