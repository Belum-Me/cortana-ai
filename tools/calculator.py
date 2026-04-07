import ast
import operator

ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node):
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.BinOp):
        op = type(node.op)
        if op not in ALLOWED_OPS:
            raise ValueError(f"Operacion no permitida: {op}")
        return ALLOWED_OPS[op](_eval_node(node.left), _eval_node(node.right))
    elif isinstance(node, ast.UnaryOp):
        op = type(node.op)
        if op not in ALLOWED_OPS:
            raise ValueError(f"Operacion no permitida: {op}")
        return ALLOWED_OPS[op](_eval_node(node.operand))
    else:
        raise ValueError(f"Tipo de nodo no permitido: {type(node)}")


def calculate(expression: str) -> str:
    """Evalua una expresion matematica de forma segura."""
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _eval_node(tree.body)
        return f"{expression} = {result}"
    except ZeroDivisionError:
        return "Error: division entre cero."
    except Exception as e:
        return f"Error al calcular '{expression}': {e}"
