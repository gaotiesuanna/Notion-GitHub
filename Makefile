.PHONY: install sync reconcile reconcile-apply test

install:
	pip install -r requirements.txt

sync:
	python scripts/sync.py

reconcile:
	python scripts/reconcile_categories_from_notion.py

reconcile-apply:
	python scripts/reconcile_categories_from_notion.py --apply

test:
	python scripts/notion_test.py
