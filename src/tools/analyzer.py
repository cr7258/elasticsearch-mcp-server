from typing import Dict, List, Optional

from fastmcp import FastMCP


class AnalyzerTools:
    def __init__(self, search_client):
        self.search_client = search_client

    def register_tools(self, mcp: FastMCP):
        @mcp.tool()
        def analyze_text(
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
            Analyze text to see how it would be tokenized.

            Use this tool to understand how Elasticsearch/OpenSearch tokenizes and
            transforms text using analyzers. This is essential for debugging search
            queries and understanding why certain documents match or don't match.

            Args:
                text: The text to analyze
                index: Index name to use its configured analyzer. If not specified,
                       uses cluster-level analysis with built-in analyzers only.
                analyzer: Name of the analyzer to use (e.g., 'standard', 'korean',
                         'korean_search'). If index is specified, you can use
                         custom analyzers defined in that index.
                tokenizer: Tokenizer to use for custom analysis chain. Cannot be
                          used together with 'analyzer'.
                filter: List of token filters to apply (e.g., ['lowercase', 'stop']).
                       Used with 'tokenizer' for custom analysis chain.
                char_filter: List of character filters to apply before tokenization.
                            Used with 'tokenizer' for custom analysis chain.
                explain: If True, returns detailed information about each token
                        including all token attributes and filter transformations.
                        Useful for debugging complex analyzer chains.
                attributes: List of token attributes to return when explain=True
                           (e.g., ['keyword', 'type']). If not specified, all
                           attributes are returned.

            Returns:
                Dict containing 'tokens' array. Each token has 'token', 'start_offset',
                'end_offset', 'type', and 'position' fields. With explain=True,
                returns detailed 'detail' object showing each filter's effect.
            """
            return self.search_client.analyze_text(
                text=text,
                index=index,
                analyzer=analyzer,
                tokenizer=tokenizer,
                filter=filter,
                char_filter=char_filter,
                explain=explain,
                attributes=attributes,
            )
