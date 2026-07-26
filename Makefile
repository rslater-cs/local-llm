up:
	docker compose up -d


down:
	docker compose down


logs:
	docker compose logs -f


status:
	docker compose ps


build:
	docker compose build


update:
	git pull
	docker compose pull
	docker compose build
	docker compose up -d


restart:
	docker compose restart