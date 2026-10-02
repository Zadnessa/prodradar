-- Выполняется только в изолированной test БД; legacy vacancies сохраняются.
BEGIN;
ALTER TABLE public.vacancies ADD COLUMN IF NOT EXISTS selection_profile text NOT NULL DEFAULT 'product';
ALTER TABLE public.vacancies ADD COLUMN IF NOT EXISTS role_families text[] NOT NULL DEFAULT '{}';
ALTER TABLE public.vacancies ADD COLUMN IF NOT EXISTS selection_version text;
CREATE INDEX IF NOT EXISTS vacancies_profile_active ON public.vacancies(selection_profile, is_active);

CREATE TABLE IF NOT EXISTS public.source_pool (
    source_name text NOT NULL,
    vacancy_id text NOT NULL,
    vacancy jsonb NOT NULL,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source_name, vacancy_id)
);
CREATE TABLE IF NOT EXISTS public.source_pool_status (
    source_name text PRIMARY KEY,
    status text NOT NULL CHECK (status IN ('ready', 'empty', 'failed')),
    captured_at timestamptz NOT NULL DEFAULT now(),
    raw_count integer NOT NULL DEFAULT 0,
    metadata jsonb NOT NULL DEFAULT '{}'
);
ALTER TABLE public.source_pool ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.source_pool_status ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.source_pool, public.source_pool_status FROM anon, authenticated;
GRANT ALL ON public.source_pool, public.source_pool_status TO service_role;

CREATE OR REPLACE FUNCTION public.replace_source_pool(p_source text, p_items jsonb, p_metadata jsonb)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER AS $$
BEGIN
    IF p_source IS NULL OR p_source = '' OR jsonb_typeof(p_items) != 'array' THEN
        RAISE EXCEPTION 'Invalid source pool';
    END IF;
    IF EXISTS (SELECT FROM jsonb_array_elements(p_items) j
               WHERE coalesce(j->>'id', '') = '' OR coalesce(j->>'title', '') = ''
                  OR coalesce(j->>'url', '') = '') THEN
        RAISE EXCEPTION 'Missing required pool fields';
    END IF;
    IF (SELECT count(*) FROM jsonb_array_elements(p_items)) !=
       (SELECT count(DISTINCT j->>'id') FROM jsonb_array_elements(p_items) j) THEN
        RAISE EXCEPTION 'Duplicate pool ids';
    END IF;
    DELETE FROM public.source_pool WHERE source_name = p_source;
    INSERT INTO public.source_pool(source_name, vacancy_id, vacancy)
      SELECT p_source, j->>'id', j FROM jsonb_array_elements(p_items) j;
    INSERT INTO public.source_pool_status(source_name, status, captured_at, raw_count, metadata)
      VALUES (p_source, CASE WHEN jsonb_array_length(p_items) = 0 THEN 'empty' ELSE 'ready' END,
              now(), jsonb_array_length(p_items), p_metadata)
      ON CONFLICT (source_name) DO UPDATE SET status = excluded.status,
        captured_at = excluded.captured_at, raw_count = excluded.raw_count, metadata = excluded.metadata;
END;
$$;
REVOKE ALL ON FUNCTION public.replace_source_pool(text, jsonb, jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.replace_source_pool(text, jsonb, jsonb) TO service_role;
NOTIFY pgrst, 'reload schema';
COMMIT;

-- Большие каталоги загружаются короткими HTTP batches, публикуются одной транзакцией.
BEGIN;
CREATE TABLE IF NOT EXISTS public.source_pool_stage (
    capture_id uuid NOT NULL,
    source_name text NOT NULL,
    vacancy_id text NOT NULL,
    vacancy jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(capture_id, vacancy_id),
    CHECK (vacancy->>'id' = vacancy_id),
    CHECK (coalesce(vacancy->>'title','') != '' AND coalesce(vacancy->>'url','') != '')
);
ALTER TABLE public.source_pool_stage ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.source_pool_stage FROM anon, authenticated;
GRANT ALL ON public.source_pool_stage TO service_role;
CREATE OR REPLACE FUNCTION public.commit_source_pool(p_source text, p_capture uuid, p_expected integer, p_metadata jsonb)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER AS $$
BEGIN
    IF p_source IS NULL OR p_source = '' OR p_expected < 0 THEN
        RAISE EXCEPTION 'Invalid source pool';
    END IF;
    PERFORM pg_advisory_xact_lock(hashtext('source_pool:' || p_source));
    IF (SELECT count(*) FROM public.source_pool_stage WHERE capture_id = p_capture AND source_name = p_source) != p_expected
       OR EXISTS(SELECT FROM public.source_pool_stage WHERE capture_id = p_capture AND source_name != p_source) THEN
        RAISE EXCEPTION 'Incomplete source pool stage';
    END IF;
    DELETE FROM public.source_pool WHERE source_name = p_source;
    INSERT INTO public.source_pool(source_name, vacancy_id, vacancy)
        SELECT source_name, vacancy_id, vacancy FROM public.source_pool_stage
        WHERE capture_id = p_capture AND source_name = p_source;
    INSERT INTO public.source_pool_status(source_name, status, captured_at, raw_count, metadata)
        VALUES(p_source, CASE WHEN p_expected = 0 THEN 'empty' ELSE 'ready' END, now(), p_expected, p_metadata)
        ON CONFLICT(source_name) DO UPDATE SET status = excluded.status, captured_at = excluded.captured_at,
            raw_count = excluded.raw_count, metadata = excluded.metadata;
    DELETE FROM public.source_pool_stage WHERE capture_id = p_capture;
    DELETE FROM public.source_pool_stage WHERE created_at < now() - interval '1 day';
END;
$$;
REVOKE ALL ON FUNCTION public.commit_source_pool(text, uuid, integer, jsonb) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.commit_source_pool(text, uuid, integer, jsonb) TO service_role;
NOTIFY pgrst, 'reload schema';
COMMIT;
