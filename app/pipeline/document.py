from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from app.pipeline.verification import is_translatable

class ASTNode(ABC):
    @abstractmethod
    def to_dict(self) -> Any:
        """Convert the AST node back to native Python types."""
        pass

class DocumentNode(ASTNode):
    def __init__(self, root: ASTNode, format_type: str):
        self.root = root
        self.format_type = format_type

    def to_dict(self) -> Any:
        return self.root.to_dict()

class ObjectNode(ASTNode):
    def __init__(self, properties: Dict[str, ASTNode]):
        self.properties = properties

    def to_dict(self) -> Dict[str, Any]:
        return {k: v.to_dict() for k, v in self.properties.items()}

class ArrayNode(ASTNode):
    def __init__(self, elements: List[ASTNode]):
        self.elements = elements

    def to_dict(self) -> List[Any]:
        return [elem.to_dict() for elem in self.elements]

class TextNode(ASTNode):
    def __init__(self, value: str, path: str, is_translatable: bool = True):
        self.value = value
        self.path = path
        self.is_translatable = is_translatable
        self.translated_value: Optional[str] = None

    def to_dict(self) -> str:
        return self.translated_value if self.translated_value is not None else self.value

class ValueNode(ASTNode):
    def __init__(self, value: Any):
        self.value = value

    def to_dict(self) -> Any:
        return self.value

def json_to_ast(data: Any, path: str = "") -> ASTNode:
    """Recursively parse JSON data (dicts/lists/primitives) into an AST structure."""
    if isinstance(data, dict):
        properties = {}
        for k, v in data.items():
            child_path = f"{path}.{k}" if path else k
            properties[k] = json_to_ast(v, child_path)
        return ObjectNode(properties)
    elif isinstance(data, list):
        elements = []
        for i, item in enumerate(data):
            child_path = f"{path}[{i}]"
            elements.append(json_to_ast(item, child_path))
        return ArrayNode(elements)
    elif isinstance(data, str):
        is_trans = is_translatable(data)
        # Skip translation if the path indicates it's an icon or icons property
        if path:
            last_key = path.split(".")[-1].split("[")[0].lower()
            if last_key in ("icon", "icons"):
                is_trans = False
        return TextNode(value=data, path=path, is_translatable=is_trans)
    else:
        return ValueNode(data)

def collect_translatable_nodes(node: ASTNode) -> List[TextNode]:
    """Traverse the AST to retrieve a list of all translatable TextNodes."""
    nodes = []
    if isinstance(node, DocumentNode):
        nodes.extend(collect_translatable_nodes(node.root))
    elif isinstance(node, ObjectNode):
        for child in node.properties.values():
            nodes.extend(collect_translatable_nodes(child))
    elif isinstance(node, ArrayNode):
        for child in node.elements:
            nodes.extend(collect_translatable_nodes(child))
    elif isinstance(node, TextNode):
        if node.is_translatable:
            nodes.append(node)
    return nodes
