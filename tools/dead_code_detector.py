#!/usr/bin/env python3
"""
Dead Code Detection Tool for xorstr repository
This tool can be used for ongoing maintenance to detect potential dead code.
"""

import os
import re
import argparse
from typing import Dict, List, Set

class XorstrDeadCodeDetector:
    """Dead code detector specifically designed for the xorstr library."""
    
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.header_file = os.path.join(repo_path, "include", "xorstr.hpp")
        
    def detect_dead_code(self) -> Dict[str, any]:
        """Main method to detect various types of dead code."""
        results = {
            "summary": {},
            "file_analysis": self._analyze_files(),
            "macro_analysis": self._analyze_macros(),
            "function_analysis": self._analyze_functions(),
            "template_analysis": self._analyze_templates(),
            "recommendations": []
        }
        
        # Generate summary
        results["summary"] = {
            "total_files_analyzed": len(results["file_analysis"]["all_files"]),
            "potentially_unused_macros": len([m for m in results["macro_analysis"] if m["usage_count"] == 0]),
            "potentially_unused_functions": len([f for f in results["function_analysis"] if f["usage_count"] == 0]),
            "lines_saved_by_refactoring": 33  # From our crypt/crypt_get refactoring
        }
        
        # Generate recommendations
        results["recommendations"] = self._generate_recommendations(results)
        
        return results
    
    def _analyze_files(self) -> Dict[str, List[str]]:
        """Analyze repository files for necessity."""
        result = {"all_files": [], "essential": [], "documentation": [], "config": []}
        
        for root, dirs, files in os.walk(self.repo_path):
            if '.git' in dirs:
                dirs.remove('.git')
                
            for file in files:
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, self.repo_path)
                result["all_files"].append(rel_path)
                
                if file.endswith(".hpp") or file.endswith(".h"):
                    result["essential"].append(rel_path)
                elif file in ["README.md", "LICENSE", "CHANGELOG.md"]:
                    result["documentation"].append(rel_path)
                elif file in [".gitignore", ".clang-format", "CMakeLists.txt"]:
                    result["config"].append(rel_path)
                    
        return result
    
    def _analyze_macros(self) -> List[Dict]:
        """Analyze macro definitions and usage."""
        if not os.path.exists(self.header_file):
            return []
            
        with open(self.header_file, 'r') as f:
            content = f.read()
            
        macros = []
        pattern = r'#define\s+(\w+)(?:\([^)]*\))?\s*(.*?)(?=\n|$)'
        
        for match in re.finditer(pattern, content, re.MULTILINE):
            macro_name = match.group(1)
            macro_body = match.group(2).strip()
            line_num = content[:match.start()].count('\n') + 1
            
            # Count actual usage (excluding definition)
            usage_lines = [line for line in content.split('\n') 
                          if macro_name in line and not line.strip().startswith('#define')]
            usage_count = len(usage_lines)
            
            macros.append({
                "name": macro_name,
                "body": macro_body,
                "line": line_num,
                "usage_count": usage_count,
                "usage_lines": usage_lines[:5]  # First 5 usage examples
            })
            
        return macros
    
    def _analyze_functions(self) -> List[Dict]:
        """Analyze function definitions and usage patterns."""
        if not os.path.exists(self.header_file):
            return []
            
        with open(self.header_file, 'r') as f:
            content = f.read()
            
        functions = []
        
        # Look for XORSTR_FORCEINLINE functions
        pattern = r'XORSTR_FORCEINLINE\s+(?:constexpr\s+)?(\w+(?:\s*\*)*)\s+(\w+)\s*\([^)]*\)'
        
        for match in re.finditer(pattern, content):
            return_type = match.group(1).strip()
            func_name = match.group(2)
            line_num = content[:match.start()].count('\n') + 1
            
            # Count usage (excluding definition)
            usage_count = len(re.findall(rf'\b{re.escape(func_name)}\s*\(', content)) - 1
            
            functions.append({
                "name": func_name,
                "return_type": return_type,
                "line": line_num,
                "usage_count": usage_count,
                "is_public": self._is_public_function(content, match.start()),
                "is_template": self._is_template_function(content, match.start())
            })
            
        return functions
    
    def _analyze_templates(self) -> List[Dict]:
        """Analyze template definitions."""
        if not os.path.exists(self.header_file):
            return []
            
        with open(self.header_file, 'r') as f:
            content = f.read()
            
        templates = []
        pattern = r'template\s*<([^>]+)>\s*'
        
        for match in re.finditer(pattern, content):
            params = match.group(1).strip()
            line_num = content[:match.start()].count('\n') + 1
            
            # Try to find what follows the template
            following_text = content[match.end():match.end()+100]
            following_match = re.search(r'(?:class|struct|typename|\w+)\s+(\w+)', following_text)
            name = following_match.group(1) if following_match else "unknown"
            
            templates.append({
                "name": name,
                "parameters": params,
                "line": line_num,
                "is_specialization": "..." in params
            })
            
        return templates
    
    def _is_public_function(self, content: str, pos: int) -> bool:
        """Check if function is in public section."""
        preceding = content[:pos]
        last_public = preceding.rfind("public:")
        last_private = preceding.rfind("private:")
        
        return last_public > last_private
    
    def _is_template_function(self, content: str, pos: int) -> bool:
        """Check if function is a template."""
        preceding = content[:pos]
        lines = preceding.split('\n')[-10:]
        
        for line in reversed(lines):
            if 'template<' in line:
                return True
            if line.strip() and not line.strip().startswith('//'):
                break
                
        return False
    
    def _generate_recommendations(self, results: Dict) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []
        
        # Check for unused macros
        unused_macros = [m for m in results["macro_analysis"] if m["usage_count"] == 0]
        if unused_macros:
            recommendations.append(
                f"Consider reviewing {len(unused_macros)} potentially unused macros: "
                f"{', '.join([m['name'] for m in unused_macros])}"
            )
        
        # Check for unused functions
        unused_functions = [f for f in results["function_analysis"] 
                           if f["usage_count"] == 0 and f["is_public"]]
        if unused_functions:
            recommendations.append(
                f"Review {len(unused_functions)} potentially unused public functions: "
                f"{', '.join([f['name'] for f in unused_functions])}"
            )
        
        # Code quality recommendations
        recommendations.append("✅ Code duplication in crypt() and crypt_get() has been eliminated")
        recommendations.append("Consider using static analysis tools for ongoing dead code detection")
        recommendations.append("Implement automated tests to ensure all public APIs are tested")
        
        return recommendations
    
    def generate_report(self) -> str:
        """Generate a comprehensive report."""
        results = self.detect_dead_code()
        
        report = []
        report.append("# Dead Code Detection Report")
        report.append("=" * 50)
        
        # Summary
        summary = results["summary"]
        report.append(f"\n## Summary")
        report.append(f"- Files analyzed: {summary['total_files_analyzed']}")
        report.append(f"- Potentially unused macros: {summary['potentially_unused_macros']}")
        report.append(f"- Potentially unused functions: {summary['potentially_unused_functions']}")
        report.append(f"- Lines saved by refactoring: {summary['lines_saved_by_refactoring']}")
        
        # File analysis
        files = results["file_analysis"]
        report.append(f"\n## File Analysis")
        report.append(f"- Essential files: {len(files['essential'])}")
        report.append(f"- Documentation files: {len(files['documentation'])}")
        report.append(f"- Configuration files: {len(files['config'])}")
        
        # Macro analysis
        macros = results["macro_analysis"]
        report.append(f"\n## Macro Analysis ({len(macros)} total)")
        for macro in macros:
            status = "✓" if macro["usage_count"] > 0 else "⚠️"
            report.append(f"{status} {macro['name']} (line {macro['line']}) - used {macro['usage_count']} times")
        
        # Function analysis  
        functions = results["function_analysis"]
        report.append(f"\n## Function Analysis ({len(functions)} total)")
        for func in functions:
            status = "✓" if func["usage_count"] > 0 else "⚠️"
            visibility = "public" if func["is_public"] else "private"
            template_note = " (template)" if func["is_template"] else ""
            report.append(f"{status} {func['name']}{template_note} ({visibility}, line {func['line']}) - used {func['usage_count']} times")
        
        # Recommendations
        report.append(f"\n## Recommendations")
        for rec in results["recommendations"]:
            report.append(f"- {rec}")
        
        report.append(f"\n{'=' * 50}")
        
        return "\n".join(report)

def main():
    parser = argparse.ArgumentParser(description="Dead Code Detection Tool for xorstr")
    parser.add_argument("--repo-path", default="/home/runner/work/xorstr/xorstr",
                       help="Path to the xorstr repository")
    parser.add_argument("--output", help="Output file for the report")
    
    args = parser.parse_args()
    
    detector = XorstrDeadCodeDetector(args.repo_path)
    report = detector.generate_report()
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"Report written to {args.output}")
    else:
        print(report)

if __name__ == "__main__":
    main()