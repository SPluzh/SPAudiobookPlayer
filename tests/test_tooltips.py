"""
Test to verify that all tooltips are properly implemented for language switching.

This test checks that:
1. All setToolTip() calls in setup_ui()/__init__() are also present in update_texts()
2. Classes with tooltips have an update_texts() method (or update_all_texts() for main window)
3. Dynamic tooltips (via method calls) are properly handled
"""

import ast
import os
from pathlib import Path
from typing import Dict, Set, List, Tuple


class TooltipAnalyzer(ast.NodeVisitor):
    """AST visitor to analyze tooltip usage in a class."""
    
    def __init__(self, class_name: str):
        self.class_name = class_name
        self.current_method = None
        
        # Tooltips found in setup_ui() or __init__()
        self.setup_tooltips: Set[str] = set()  # widget names
        
        # Tooltips found in update_texts()
        self.update_tooltips: Set[str] = set()  # widget names
        
        # Methods that contain setToolTip() calls
        self.methods_with_tooltips: Dict[str, Set[str]] = {}
        
        # Method calls in update_texts()
        self.update_method_calls: Set[str] = set()
        
        # Delegated update_texts() calls (e.g., self.widget.update_texts())
        self.delegated_updates: Set[str] = set()
        
        # Track if class has update_texts() or update_all_texts() method
        self.has_update_texts = False
        
        # List of methods that are considered "update methods"
        self.UPDATE_METHOD_NAMES = ('update_texts', 'update_all_texts')
        # List of methods that are considered "setup methods"
        self.SETUP_METHOD_NAMES = ('setup_ui', '__init__')
        
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function/method definitions."""
        old_method = self.current_method
        self.current_method = node.name
        
        # Accept both update_texts() and update_all_texts()
        if node.name in self.UPDATE_METHOD_NAMES:
            self.has_update_texts = True
        
        self.generic_visit(node)
        self.current_method = old_method
        
    def visit_Call(self, node: ast.Call):
        """Visit function calls to find setToolTip() and method calls."""
        # Check if this is a setToolTip() call
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'setToolTip':
            widget_name = self._get_widget_name(node.func.value)
            
            if widget_name:
                # Track which method contains this tooltip
                if self.current_method:
                    if self.current_method not in self.methods_with_tooltips:
                        self.methods_with_tooltips[self.current_method] = set()
                    self.methods_with_tooltips[self.current_method].add(widget_name)
                
                # Track tooltips in setup methods
                if self.current_method in self.SETUP_METHOD_NAMES:
                    self.setup_tooltips.add(widget_name)
                
                # Track tooltips in update methods
                elif self.current_method in self.UPDATE_METHOD_NAMES:
                    self.update_tooltips.add(widget_name)
        
        # Check for method calls in update methods
        if self.current_method in self.UPDATE_METHOD_NAMES:
            # Direct method call: self.some_method()
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == 'self':
                    self.update_method_calls.add(node.func.attr)
                
                # Delegated update_texts(): self.widget.update_texts()
                if node.func.attr in self.UPDATE_METHOD_NAMES:
                    widget_name = self._get_widget_name(node.func.value)
                    if widget_name:
                        self.delegated_updates.add(widget_name)
        
        self.generic_visit(node)
    
    def _get_widget_name(self, node) -> str:
        """Extract widget name from AST node."""
        if isinstance(node, ast.Attribute):
            # self.button -> "button"
            if isinstance(node.value, ast.Name) and node.value.id == 'self':
                return node.attr
        elif isinstance(node, ast.Name) and node.id == 'self':
            # self -> "self" (for self.setToolTip() calls)
            return "self"
        return ""
    
    def get_coverage(self) -> Tuple[Set[str], Set[str]]:
        """
        Calculate which tooltips are covered in update_texts().
        
        Returns:
            (covered_widgets, missing_widgets)
        """
        covered = set()
        
        # 1. Direct tooltips in update_texts()
        covered.update(self.update_tooltips)
        
        # 2. Tooltips covered by method calls
        for method_name in self.update_method_calls:
            if method_name in self.methods_with_tooltips:
                covered.update(self.methods_with_tooltips[method_name])
        
        # 3. Tooltips covered by delegated update_texts() calls
        covered.update(self.delegated_updates)
        
        missing = self.setup_tooltips - covered
        
        return covered, missing


def analyze_file(file_path: Path) -> Dict[str, TooltipAnalyzer]:
    """
    Analyze a Python file for tooltip usage.
    
    Returns:
        Dict mapping class names to their TooltipAnalyzer
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content, filename=str(file_path))
    except Exception as e:
        print(f"  ⚠️  Error parsing {file_path.name}: {e}")
        return {}
    
    results = {}
    
    # Find all class definitions
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            analyzer = TooltipAnalyzer(node.name)
            analyzer.visit(node)
            
            # Only include classes that have tooltips in setup
            if analyzer.setup_tooltips:
                results[node.name] = analyzer
    
    return results


def scan_project(project_root: Path) -> Dict[str, Dict[str, TooltipAnalyzer]]:
    """
    Scan entire project for tooltip usage.
    
    Returns:
        Dict mapping file paths to their class analyzers
    """
    results = {}
    
    for root, dirs, files in os.walk(project_root):
        # Skip certain directories
        dirs[:] = [d for d in dirs if d not in ('_build_', '.venv', '__pycache__', '.git', 'tests')]
        
        for file in files:
            if file.endswith('.py') and file not in ('test_tooltips.py', 'check_translations.py'):
                file_path = Path(root) / file
                
                analyzers = analyze_file(file_path)
                if analyzers:
                    # Store relative path for cleaner output
                    try:
                        rel_path = file_path.relative_to(project_root)
                    except ValueError:
                        rel_path = file_path
                    results[str(rel_path)] = analyzers
    
    return results


def print_report(results: Dict[str, Dict[str, TooltipAnalyzer]]):
    """Print detailed report of tooltip coverage."""
    
    print("\n" + "=" * 70)
    print("TOOLTIP COVERAGE REPORT")
    print("=" * 70)
    
    total_classes = 0
    passed = 0
    warnings = 0
    errors = 0
    
    for file_path, analyzers in sorted(results.items()):
        print(f"\nFile: {file_path}")
        print("-" * 70)
        
        for class_name, analyzer in sorted(analyzers.items()):
            total_classes += 1
            
            print(f"\n  Class: {class_name}")
            print(f"    Tooltips in setup_ui()/__init__(): {len(analyzer.setup_tooltips)}")
            
            if analyzer.setup_tooltips:
                print(f"      Widgets: {', '.join(sorted(analyzer.setup_tooltips))}")
            
            # Check if update_texts() exists
            if not analyzer.has_update_texts:
                print(f"    [ERROR] Missing update_texts() or update_all_texts() method!")
                print(f"       All tooltips will not update on language change.")
                errors += 1
                continue
            
            # Check coverage
            covered, missing = analyzer.get_coverage()
            
            print(f"    Tooltips covered in update_texts(): {len(covered)}")
            if covered:
                print(f"      Widgets: {', '.join(sorted(covered))}")
            
            # Show how coverage is achieved
            if analyzer.update_tooltips:
                print(f"      |- Direct setToolTip() calls: {', '.join(sorted(analyzer.update_tooltips))}")
            
            if analyzer.update_method_calls:
                methods_covering = []
                for method in sorted(analyzer.update_method_calls):
                    if method in analyzer.methods_with_tooltips:
                        widgets = analyzer.methods_with_tooltips[method]
                        methods_covering.append(f"{method}() [{', '.join(sorted(widgets))}]")
                if methods_covering:
                    print(f"      |- Via method calls: {', '.join(methods_covering)}")
            
            if analyzer.delegated_updates:
                print(f"      +- Delegated update_texts(): {', '.join(sorted(analyzer.delegated_updates))}")
            
            # Report missing coverage
            if missing:
                print(f"    [ERROR] {len(missing)} tooltip(s) NOT covered in update_texts()!")
                print(f"       Missing widgets: {', '.join(sorted(missing))}")
                errors += 1
            else:
                print(f"    [PASS] All tooltips properly covered!")
                passed += 1
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total classes with tooltips: {total_classes}")
    print(f"[PASS] Passed: {passed}")
    print(f"[WARN] Warnings: {warnings}")
    print(f"[ERROR] Errors: {errors}")
    
    if errors == 0:
        print("\nAll tooltips are properly implemented for language switching!")
    else:
        print(f"\nFound {errors} issue(s) that need attention.")
    
    print("=" * 70)


def main():
    """Main entry point."""
    # Detect project root by looking for .git or common project files
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent
    
    # Verify we are in the right place
    if not (project_root / "main.py").exists():
        # Try one more level if needed
        if (project_root.parent / "main.py").exists():
            project_root = project_root.parent
    
    print(f"Project root: {project_root}")
    print(f"Scanning for tooltip usage...")
    
    results = scan_project(project_root)
    
    if not results:
        print("\n⚠️  No classes with tooltips found!")
        return
    
    print_report(results)


if __name__ == "__main__":
    main()
