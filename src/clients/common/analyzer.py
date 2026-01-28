from typing import Dict, List, Optional

from src.clients.base import SearchClientBase


class AnalyzerClient(SearchClientBase):
    def analyze_text(
        self,
        text: str,
        index: Optional[str] = None,
        analyzer: Optional[str] = None,
        tokenizer: Optional[str] = None,
        filter: Optional[List[str]] = None,
        char_filter: Optional[List[str]] = None,
        explain: bool = False,
        attributes: Optional[List[str]] = None,
    ) -> Dict:
        """
        Analyze text using the specified analyzer or custom analysis chain.

        Args:
            text: The text to analyze
            index: Index to derive analyzer from (optional)
            analyzer: Analyzer name to use (optional)
            tokenizer: Tokenizer to use for custom analysis (optional)
            filter: Token filters to apply (optional)
            char_filter: Character filters to apply (optional)
            explain: Whether to return detailed token analysis (optional)
            attributes: Token attributes to return when explain=True (optional)

        Returns:
            Analysis result with tokens
        """
        body = {"text": text}

        if analyzer:
            body["analyzer"] = analyzer
        if tokenizer:
            body["tokenizer"] = tokenizer
        if filter:
            body["filter"] = filter
        if char_filter:
            body["char_filter"] = char_filter
        if explain:
            body["explain"] = explain
        if attributes:
            body["attributes"] = attributes

        if index:
            return self.client.indices.analyze(index=index, body=body)
        else:
            return self.client.indices.analyze(body=body)
