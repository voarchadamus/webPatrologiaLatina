# web Patrologia Latina
1. clone repo
2. browse through the html pages
3. to restyle edit `SGML/assets/tree_style.css` and run ```python SGML/SGML_tools/batch_gen.py --volumes-dir SGML/Volumes --pages-dir SGML/Pages```, the main generation logic is in ```SGML/SGML_tools/gen_sgml_page.py```
4. to generate index run ```python SGML/SGML_tools/gen_index.py --out SGML/index.html```
5. if you're curious about the SGML structures you can run the command given in ```SGML/SGML_tools/convert_sgml.py```
