import ast
import networkx as nx


# ============================================================
# PARSE PYTHON FILE
# ============================================================

def get_ast_tree(file_path):
    """
    Parse a Python file and return its AST tree.

    UTF-8 is tried first.
    If the file contains Windows/legacy characters,
    cp1252 is used as a fallback.
    """

    encodings = ["utf-8", "cp1252", "latin-1"]

    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                source = f.read()

            return ast.parse(source)

        except UnicodeDecodeError:
            continue

    raise UnicodeDecodeError(
        "unknown",
        b"",
        0,
        1,
        f"Could not decode file: {file_path}"
    )


# ============================================================
# FUNCTION / CLASS VISITOR
# ============================================================

class FunctionVisitor(ast.NodeVisitor):

    def __init__(self):
        self.current_function = None

        self.functions = set()
        self.classes = set()

        self.edges = []

    # --------------------------------------------------------
    # FUNCTION
    # --------------------------------------------------------

    def visit_FunctionDef(self, node):

        function_name = node.name

        self.functions.add(function_name)

        previous_function = self.current_function

        self.current_function = function_name

        self.generic_visit(node)

        self.current_function = previous_function

    # --------------------------------------------------------
    # ASYNC FUNCTION
    # --------------------------------------------------------

    def visit_AsyncFunctionDef(self, node):

        function_name = node.name

        self.functions.add(function_name)

        previous_function = self.current_function

        self.current_function = function_name

        self.generic_visit(node)

        self.current_function = previous_function

    # --------------------------------------------------------
    # CLASS
    # --------------------------------------------------------

    def visit_ClassDef(self, node):

        class_name = node.name

        self.classes.add(class_name)

        self.generic_visit(node)

    # --------------------------------------------------------
    # FUNCTION CALL
    # --------------------------------------------------------

    def visit_Call(self, node):

        if self.current_function:

            # Example:
            # foo()

            if isinstance(node.func, ast.Name):

                called_function = node.func.id

                self.edges.append(
                    (
                        self.current_function,
                        called_function
                    )
                )

            # Example:
            # obj.method()

            elif isinstance(node.func, ast.Attribute):

                called_method = node.func.attr

                self.edges.append(
                    (
                        self.current_function,
                        called_method
                    )
                )

        self.generic_visit(node)


# ============================================================
# BUILD DEPENDENCY GRAPH
# ============================================================

def build_dependency_graph(file_path):

    tree = get_ast_tree(file_path)

    visitor = FunctionVisitor()

    visitor.visit(tree)

    G = nx.DiGraph()

    # --------------------------------------------------------
    # Add functions
    # --------------------------------------------------------

    for function in sorted(visitor.functions):

        G.add_node(
            function,
            type="function"
        )

    # --------------------------------------------------------
    # Add classes
    # --------------------------------------------------------

    for class_name in sorted(visitor.classes):

        G.add_node(
            class_name,
            type="class"
        )

    # --------------------------------------------------------
    # Add only meaningful edges
    # --------------------------------------------------------

    valid_functions = visitor.functions
    valid_classes = visitor.classes

    valid_nodes = valid_functions | valid_classes

    for source, target in visitor.edges:

        # Only show relationships where target
        # actually exists in this file.
        if (
            source != target
            and source in valid_nodes
            and target in valid_nodes
        ):
            G.add_edge(
                source,
                target,
                relationship="calls"
            )

    return G


# ============================================================
# CREATE CLEAN GRAPH
# ============================================================

def draw_dependency_graph(G, output_path=None):

    import matplotlib.pyplot as plt

    if G.number_of_nodes() == 0:

        print("No functions or classes found.")

        return

    # --------------------------------------------------------
    # Dynamic figure size
    # --------------------------------------------------------

    node_count = G.number_of_nodes()

    width = max(10, min(20, node_count * 1.2))
    height = max(7, min(16, node_count * 0.8))

    plt.figure(
        figsize=(width, height)
    )

    # --------------------------------------------------------
    # Better layout
    # --------------------------------------------------------

    if node_count <= 8:

        pos = nx.spring_layout(
            G,
            seed=42,
            k=2.5,
            iterations=100
        )

    elif node_count <= 20:

        pos = nx.spring_layout(
            G,
            seed=42,
            k=3.5,
            iterations=150
        )

    else:

        pos = nx.spring_layout(
            G,
            seed=42,
            k=5,
            iterations=200
        )

    # --------------------------------------------------------
    # Node colors
    # --------------------------------------------------------

    node_colors = []

    for node in G.nodes():

        node_type = G.nodes[node].get(
            "type",
            "function"
        )

        if node_type == "class":
            node_colors.append("orange")
        else:
            node_colors.append("skyblue")

    # --------------------------------------------------------
    # Draw nodes
    # --------------------------------------------------------

    nx.draw_networkx_nodes(
        G,
        pos,
        node_color=node_colors,
        node_size=2200,
        alpha=0.95
    )

    # --------------------------------------------------------
    # Draw edges
    # --------------------------------------------------------

    nx.draw_networkx_edges(
        G,
        pos,
        arrows=True,
        arrowsize=20,
        edge_color="gray",
        width=1.5,
        connectionstyle="arc3,rad=0.08"
    )

    # --------------------------------------------------------
    # Draw labels
    # --------------------------------------------------------

    nx.draw_networkx_labels(
        G,
        pos,
        font_size=9,
        font_weight="bold"
    )

    # --------------------------------------------------------
    # Edge labels
    # --------------------------------------------------------

    edge_labels = {}

    for source, target in G.edges():

        edge_labels[
            (source, target)
        ] = "calls"

    nx.draw_networkx_edge_labels(
        G,
        pos,
        edge_labels=edge_labels,
        font_size=7
    )

    # --------------------------------------------------------
    # Title
    # --------------------------------------------------------

    plt.title(
        "Function & Class Dependency Graph",
        fontsize=16,
        fontweight="bold"
    )

    plt.axis("off")

    plt.tight_layout()

    # --------------------------------------------------------
    # Save or show
    # --------------------------------------------------------

    if output_path:

        plt.savefig(
            output_path,
            dpi=150,
            bbox_inches="tight"
        )

        plt.close()

    else:

        plt.show()