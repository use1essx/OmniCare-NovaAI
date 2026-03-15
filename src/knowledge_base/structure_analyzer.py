"""
Document structure analyzer for semantic chunking.

This module provides rule-based analysis of document structure without AI.
It detects markdown headings, lists, tables, and code blocks to help the
semantic chunker preserve document structure during chunking.
"""

import re
from typing import List, Tuple

from .semantic_types import StructureInfo, HeadingNode


class StructureAnalyzer:
    """
    Analyzes document structure using rule-based pattern matching.
    
    This class identifies structural elements in markdown documents including
    headings, lists (ordered and unordered), tables, and code blocks. The
    analysis is performed without AI to provide fast, deterministic structure
    detection that guides the semantic chunking process.
    
    The analyzer detects:
    - Markdown headings (# through ######) with their positions and levels
    - Ordered lists (1. 2. 3. etc.)
    - Unordered lists (- * +)
    - Markdown tables (| column | column |)
    - Fenced code blocks (``` or ~~~)
    
    Attributes:
        None (stateless analyzer)
    
    Example:
        >>> analyzer = StructureAnalyzer()
        >>> content = "# Title\\n\\nSome text\\n\\n- Item 1\\n- Item 2"
        >>> structure = analyzer.analyze(content)
        >>> len(structure.headings)
        1
        >>> len(structure.lists)
        1
    """
    
    # Regex patterns for structure detection
    HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    ORDERED_LIST_PATTERN = re.compile(r'^\d+\.\s+.+$', re.MULTILINE)
    UNORDERED_LIST_PATTERN = re.compile(r'^[-*+]\s+.+$', re.MULTILINE)
    TABLE_ROW_PATTERN = re.compile(r'^\|.+\|$', re.MULTILINE)
    CODE_FENCE_PATTERN = re.compile(r'^```|^~~~', re.MULTILINE)
    
    def analyze(self, content: str) -> StructureInfo:
        """
        Analyze document structure and return detected elements.
        
        Performs rule-based analysis to identify all structural elements in
        the document. This method is the main entry point for structure analysis.
        
        Args:
            content: The full document text to analyze
            
        Returns:
            StructureInfo object containing all detected structural elements
            with their positions and metadata
            
        Example:
            >>> analyzer = StructureAnalyzer()
            >>> structure = analyzer.analyze("# Heading\\n\\nText\\n\\n- List")
            >>> structure.headings[0]
            (0, 1, 'Heading')
        """
        headings = self._detect_headings(content)
        lists = self._detect_lists(content)
        tables = self._detect_tables(content)
        code_blocks = self._detect_code_blocks(content)
        heading_hierarchy = self._build_heading_hierarchy(headings)
        heading_tree = self._build_heading_tree(headings, len(content))
        position_to_heading = self._build_position_map(heading_tree)
        
        return StructureInfo(
            headings=headings,
            lists=lists,
            tables=tables,
            code_blocks=code_blocks,
            heading_hierarchy=heading_hierarchy,
            heading_tree=heading_tree,
            position_to_heading=position_to_heading
        )
    
    def _detect_headings(self, content: str) -> List[Tuple[int, int, str]]:
        """
        Detect markdown headings and extract their positions, levels, and text.
        
        Identifies headings from # (level 1) through ###### (level 6) and
        records their character position in the document, heading level, and
        the heading text content.
        
        Args:
            content: Document text to analyze
            
        Returns:
            List of tuples (position, level, text) where:
            - position: Character offset of the heading in the document
            - level: Heading level (1-6)
            - text: Heading text content (without # markers)
            
        Example:
            >>> analyzer = StructureAnalyzer()
            >>> headings = analyzer._detect_headings("# Title\\n## Subtitle")
            >>> headings
            [(0, 1, 'Title'), (8, 2, 'Subtitle')]
        """
        headings = []
        for match in self.HEADING_PATTERN.finditer(content):
            position = match.start()
            level = len(match.group(1))  # Count # characters
            text = match.group(2).strip()
            headings.append((position, level, text))
        return headings
    
    def _detect_lists(self, content: str) -> List[Tuple[int, int]]:
        """
        Detect both ordered and unordered lists and return their positions.
        
        Identifies contiguous list blocks (both ordered like "1. item" and
        unordered like "- item" or "* item") and returns the start and end
        positions of each complete list block.
        
        Args:
            content: Document text to analyze
            
        Returns:
            List of tuples (start_pos, end_pos) representing the character
            positions of complete list blocks
            
        Example:
            >>> analyzer = StructureAnalyzer()
            >>> content = "Text\\n\\n- Item 1\\n- Item 2\\n\\nMore text"
            >>> lists = analyzer._detect_lists(content)
            >>> len(lists)
            1
        """
        lists = []
        
        # Detect ordered lists
        lists.extend(self._detect_list_blocks(content, self.ORDERED_LIST_PATTERN))
        
        # Detect unordered lists
        lists.extend(self._detect_list_blocks(content, self.UNORDERED_LIST_PATTERN))
        
        # Sort by position and merge overlapping ranges
        lists.sort(key=lambda x: x[0])
        return self._merge_overlapping_ranges(lists)
    
    def _detect_list_blocks(
        self,
        content: str,
        pattern: re.Pattern
    ) -> List[Tuple[int, int]]:
        """
        Detect contiguous blocks of list items matching a pattern.
        
        Helper method that identifies consecutive list items and groups them
        into complete list blocks. A list block ends when a non-list line
        (excluding blank lines) is encountered.
        
        Args:
            content: Document text to analyze
            pattern: Compiled regex pattern for list item detection
            
        Returns:
            List of tuples (start_pos, end_pos) for each list block
        """
        blocks = []
        lines = content.split('\n')
        current_block_start = None
        current_block_end = None
        position = 0
        
        for line in lines:
            line_length = len(line) + 1  # +1 for newline
            
            if pattern.match(line):
                if current_block_start is None:
                    current_block_start = position
                current_block_end = position + line_length
            elif line.strip() == '':
                # Blank line - continue current block if exists
                pass
            else:
                # Non-list, non-blank line - end current block
                if current_block_start is not None:
                    blocks.append((current_block_start, current_block_end))
                    current_block_start = None
                    current_block_end = None
            
            position += line_length
        
        # Add final block if exists
        if current_block_start is not None:
            blocks.append((current_block_start, current_block_end))
        
        return blocks
    
    def _detect_tables(self, content: str) -> List[Tuple[int, int]]:
        """
        Detect markdown tables and return their positions.
        
        Identifies markdown table blocks by finding consecutive lines that
        match the table row pattern (lines with | delimiters). A table block
        consists of contiguous table rows.
        
        Args:
            content: Document text to analyze
            
        Returns:
            List of tuples (start_pos, end_pos) representing the character
            positions of complete table blocks
            
        Example:
            >>> analyzer = StructureAnalyzer()
            >>> content = "| Col1 | Col2 |\\n|------|------|\\n| A | B |"
            >>> tables = analyzer._detect_tables(content)
            >>> len(tables)
            1
        """
        tables = []
        lines = content.split('\n')
        current_table_start = None
        current_table_end = None
        position = 0
        
        for line in lines:
            line_length = len(line) + 1  # +1 for newline
            
            if self.TABLE_ROW_PATTERN.match(line):
                if current_table_start is None:
                    current_table_start = position
                current_table_end = position + line_length
            else:
                # Non-table line - end current table
                if current_table_start is not None:
                    tables.append((current_table_start, current_table_end))
                    current_table_start = None
                    current_table_end = None
            
            position += line_length
        
        # Add final table if exists
        if current_table_start is not None:
            tables.append((current_table_start, current_table_end))
        
        return tables
    
    def _detect_code_blocks(self, content: str) -> List[Tuple[int, int]]:
        """
        Detect fenced code blocks and return their positions.
        
        Identifies code blocks delimited by ``` or ~~~ fences. Tracks opening
        and closing fences to determine complete code block boundaries.
        
        Args:
            content: Document text to analyze
            
        Returns:
            List of tuples (start_pos, end_pos) representing the character
            positions of complete code blocks (including fence markers)
            
        Example:
            >>> analyzer = StructureAnalyzer()
            >>> content = "Text\\n\\n```python\\ncode\\n```\\n\\nMore text"
            >>> blocks = analyzer._detect_code_blocks(content)
            >>> len(blocks)
            1
        """
        code_blocks = []
        matches = list(self.CODE_FENCE_PATTERN.finditer(content))
        
        # Pair up opening and closing fences
        i = 0
        while i < len(matches) - 1:
            start_match = matches[i]
            end_match = matches[i + 1]
            
            start_pos = start_match.start()
            # Find the end of the closing fence line
            end_line_end = content.find('\n', end_match.end())
            if end_line_end == -1:
                end_line_end = len(content)
            else:
                end_line_end += 1  # Include the newline
            
            code_blocks.append((start_pos, end_line_end))
            i += 2  # Skip to next pair
        
        return code_blocks
    
    def _build_heading_hierarchy(
        self,
        headings: List[Tuple[int, int, str]]
    ) -> dict:
        """
        Build a heading hierarchy map for quick context lookup.
        
        Creates a dictionary mapping character positions to heading information
        for efficient lookup of heading context during chunking.
        
        Args:
            headings: List of detected headings as (position, level, text) tuples
            
        Returns:
            Dictionary mapping position to (level, text) tuples
            
        Example:
            >>> analyzer = StructureAnalyzer()
            >>> headings = [(0, 1, 'Title'), (100, 2, 'Subtitle')]
            >>> hierarchy = analyzer._build_heading_hierarchy(headings)
            >>> hierarchy[0]
            (1, 'Title')
        """
        return {pos: (level, text) for pos, level, text in headings}
    
    def _build_heading_tree(
        self,
        headings: List[Tuple[int, int, str]],
        content_length: int
    ) -> List[HeadingNode]:
        """
        Build a hierarchical tree of headings with parent-child relationships.
        
        Creates HeadingNode objects for each heading and establishes parent-child
        relationships based on heading levels. Lower-level headings (e.g., ##)
        become children of higher-level headings (e.g., #).
        
        Args:
            headings: List of detected headings as (position, level, text) tuples
            content_length: Total length of document content for end position calculation
            
        Returns:
            List of root-level HeadingNode objects (level 1 headings or orphaned headings)
            
        Example:
            >>> analyzer = StructureAnalyzer()
            >>> headings = [(0, 1, 'Title'), (50, 2, 'Subtitle'), (100, 2, 'Another')]
            >>> tree = analyzer._build_heading_tree(headings, 200)
            >>> len(tree)
            1
            >>> len(tree[0].children)
            2
        """
        if not headings:
            return []
        
        # Create HeadingNode objects with initial end positions
        nodes = []
        for i, (position, level, text) in enumerate(headings):
            # Calculate end position (start of next heading or end of document)
            if i < len(headings) - 1:
                end_pos = headings[i + 1][0]
            else:
                end_pos = content_length
            
            node = HeadingNode(
                position=position,
                level=level,
                text=text,
                start_pos=position,
                end_pos=end_pos,
                parent=None,
                children=[]
            )
            nodes.append(node)
        
        # Build parent-child relationships
        root_nodes = []
        stack = []  # Stack to track potential parent nodes
        
        for node in nodes:
            # Pop nodes from stack that are not valid parents (same or higher level)
            while stack and stack[-1].level >= node.level:
                stack.pop()
            
            # If stack is not empty, the top node is the parent
            if stack:
                parent = stack[-1]
                parent.children.append(node)
                node.parent = parent
            else:
                # No parent, this is a root node
                root_nodes.append(node)
            
            # Add current node to stack as potential parent for subsequent nodes
            stack.append(node)
        
        return root_nodes
    
    def _build_position_map(
        self,
        heading_tree: List[HeadingNode]
    ) -> dict:
        """
        Build a map from positions to heading nodes for quick lookup.
        
        Creates a dictionary that maps character positions to the HeadingNode
        that contains that position. This enables efficient lookup of heading
        context for any position in the document.
        
        Args:
            heading_tree: List of root-level HeadingNode objects
            
        Returns:
            Dictionary mapping positions to HeadingNode objects
            
        Example:
            >>> analyzer = StructureAnalyzer()
            >>> # After building tree...
            >>> position_map = analyzer._build_position_map(tree)
            >>> position_map[75].text
            'Subtitle'
        """
        position_map = {}
        
        def add_node_and_children(node: HeadingNode):
            """Recursively add node and its children to position map."""
            # Map the heading's start position to the node
            position_map[node.position] = node
            
            # Recursively process children
            for child in node.children:
                add_node_and_children(child)
        
        # Process all root nodes and their descendants
        for root in heading_tree:
            add_node_and_children(root)
        
        return position_map
    
    def _merge_overlapping_ranges(
        self,
        ranges: List[Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
        """
        Merge overlapping or adjacent position ranges.
        
        Helper method to consolidate overlapping ranges that may occur when
        detecting different types of lists or structures.
        
        Args:
            ranges: List of (start, end) position tuples, must be sorted
            
        Returns:
            List of merged (start, end) position tuples with no overlaps
            
        Example:
            >>> analyzer = StructureAnalyzer()
            >>> ranges = [(0, 10), (5, 15), (20, 30)]
            >>> analyzer._merge_overlapping_ranges(ranges)
            [(0, 15), (20, 30)]
        """
        if not ranges:
            return []
        
        merged = [ranges[0]]
        
        for current_start, current_end in ranges[1:]:
            last_start, last_end = merged[-1]
            
            # Check if current range overlaps or is adjacent to last range
            if current_start <= last_end:
                # Merge by extending the last range
                merged[-1] = (last_start, max(last_end, current_end))
            else:
                # No overlap, add as new range
                merged.append((current_start, current_end))
        
        return merged
