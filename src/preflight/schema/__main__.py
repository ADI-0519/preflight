from preflight.schema import WEB_SCHEMA, write_web_schema

write_web_schema()
print(f"JSON Schema -> {WEB_SCHEMA}")
