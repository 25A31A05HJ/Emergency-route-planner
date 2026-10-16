"""Self-balancing AVL tree: key = medical specialty, value = list of hospitals."""
from __future__ import annotations


class AVLNode:
    __slots__ = ("key", "values", "left", "right", "height")

    def __init__(self, key, value):
        self.key = key
        self.values = [value]
        self.left = None
        self.right = None
        self.height = 1


class AVLTree:
    def __init__(self):
        self.root = None
        self.rotations = 0
        self._keys = 0

    # ---------- helpers ----------
    @staticmethod
    def _h(node) -> int:
        return node.height if node else 0

    def _update(self, node) -> None:
        node.height = 1 + max(self._h(node.left), self._h(node.right))

    def _balance(self, node) -> int:
        return self._h(node.left) - self._h(node.right) if node else 0

    def _rot_right(self, y):
        x = y.left
        y.left = x.right
        x.right = y
        self._update(y)
        self._update(x)
        self.rotations += 1
        return x

    def _rot_left(self, x):
        y = x.right
        x.right = y.left
        y.left = x
        self._update(x)
        self._update(y)
        self.rotations += 1
        return y

    def _rebalance(self, node):
        self._update(node)
        b = self._balance(node)
        if b > 1:                                   # left heavy
            if self._balance(node.left) < 0:        # Left-Right case
                node.left = self._rot_left(node.left)
            return self._rot_right(node)
        if b < -1:                                  # right heavy
            if self._balance(node.right) > 0:       # Right-Left case
                node.right = self._rot_right(node.right)
            return self._rot_left(node)
        return node

    # ---------- public API ----------
    def insert(self, key: str, value) -> None:
        self.root = self._insert(self.root, key, value)

    def _insert(self, node, key, value):
        if node is None:
            self._keys += 1
            return AVLNode(key, value)
        k, nk = key.lower(), node.key.lower()
        if k < nk:
            node.left = self._insert(node.left, key, value)
        elif k > nk:
            node.right = self._insert(node.right, key, value)
        else:
            node.values.append(value)
            return node
        return self._rebalance(node)

    def search(self, key: str):
        """Returns (values, comparisons, path_of_keys)."""
        node, comparisons, path = self.root, 0, []
        k = key.lower()
        while node:
            comparisons += 1
            path.append(node.key)
            nk = node.key.lower()
            if k == nk:
                return list(node.values), comparisons, path
            node = node.left if k < nk else node.right
        return [], comparisons, path

    def inorder(self):
        out = []

        def walk(n):
            if n:
                walk(n.left)
                out.append((n.key, list(n.values)))
                walk(n.right)

        walk(self.root)
        return out

    @property
    def height(self) -> int:
        return self._h(self.root)

    def __len__(self) -> int:
        return self._keys

    def to_dot(self) -> str:
        lines = ["digraph AVL {",
                 'node [shape=box, style="rounded,filled", fillcolor="#ffebee", '
                 'color="#c62828", fontname="Helvetica"];',
                 'edge [color="#7f0000"];']
        counter = [0]

        def walk(n):
            if n is None:
                return None
            my_id = counter[0]
            counter[0] += 1
            label = f"+ {n.key}\\n{len(n.values)} hospital(s)\\nheight={n.height}"
            lines.append(f'n{my_id} [label="{label}"];')
            for child in (walk(n.left), walk(n.right)):
                if child is not None:
                    lines.append(f"n{my_id} -> n{child};")
            return my_id

        walk(self.root)
        lines.append("}")
        return "\n".join(lines)
