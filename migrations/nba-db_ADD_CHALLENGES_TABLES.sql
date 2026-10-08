-- ============================================================
-- Таблицы справочников (должны быть созданы первыми)
-- ============================================================

-- Категории челленджей
CREATE TABLE public.challenges_categories (
    id integer NOT NULL,
    name character varying(100) NOT NULL
);

ALTER TABLE public.challenges_categories ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.challenges_categories_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

-- Сложности челленджей
CREATE TABLE public.challenges_difficulties (
    id smallint NOT NULL,
    name character varying(50) NOT NULL
);

ALTER TABLE public.challenges_difficulties ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.challenges_difficulties_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

-- Статусы челленджей
CREATE TABLE public.challenges_statuses (
    id smallint NOT NULL,
    title character varying(50) NOT NULL
);

ALTER TABLE public.challenges_statuses ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.challenges_statuses_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

-- Статусы наборов заданий
CREATE TABLE public.tasks_set_statuses (
    id smallint NOT NULL,
    title character varying(50) NOT NULL
);

ALTER TABLE public.tasks_set_statuses ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.tasks_set_statuses_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

-- Статусы пользовательских челленджей
CREATE TABLE public.user_challenges_statuses (
    id smallint NOT NULL,
    title character varying(50) NOT NULL
);

ALTER TABLE public.user_challenges_statuses ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.user_challenges_statuses_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

-- ============================================================
-- Основные таблицы
-- ============================================================

-- Челленджи
CREATE TABLE public.challenges (
    id integer NOT NULL,
    category_id smallint NOT NULL,
    descr character varying(2048) NOT NULL
);

ALTER TABLE public.challenges ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.challenges_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

-- Награды за челленджи
CREATE TABLE public.challenges_rewards (
    id bigint NOT NULL,
    goal integer DEFAULT 1 NOT NULL,
    challenge_id integer NOT NULL,
    challenge_difficulty_id smallint NOT NULL,
    reward_exp integer DEFAULT 0 NOT NULL,
    reward_try integer DEFAULT 0 NOT NULL,
    reward_throw integer DEFAULT 0 NOT NULL
);

ALTER TABLE public.challenges_rewards ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.challenges_rewards_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

-- Наборы заданий пользователей
CREATE TABLE public.challenges_tasks_set (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    started_at timestamp without time zone DEFAULT now() NOT NULL,
    status smallint NOT NULL
);

ALTER TABLE public.challenges_tasks_set ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.challenges_tasks_set_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

-- Персональная выборка челленджей пользователя
CREATE TABLE public.challenges_user_layout (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    challenge_id integer NOT NULL
);

ALTER TABLE public.challenges_user_layout ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.challenges_user_layout_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

-- Пользовательские челленджи
CREATE TABLE public.user_challenges (
    id bigint NOT NULL,
    challenge_id integer NOT NULL,
    challenge_difficulty_id smallint NOT NULL,
    progress integer DEFAULT 0 NOT NULL,
    status smallint DEFAULT 1 NOT NULL,
    task_set_id bigint NOT NULL,
    slot smallint DEFAULT 1 NOT NULL
);

ALTER TABLE public.user_challenges ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.user_challenges_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);

-- ============================================================
-- PRIMARY KEY constraints
-- ============================================================

ALTER TABLE ONLY public.challenges_categories
    ADD CONSTRAINT challenges_categories_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.challenges_difficulties
    ADD CONSTRAINT challenges_difficulties_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.challenges_statuses
    ADD CONSTRAINT challenges_statuses_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.tasks_set_statuses
    ADD CONSTRAINT tasks_set_statuses_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.user_challenges_statuses
    ADD CONSTRAINT user_challenges_statuses_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.challenges
    ADD CONSTRAINT challenges_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.challenges
    ADD CONSTRAINT challenges_descr_key UNIQUE (descr);

ALTER TABLE ONLY public.challenges_rewards
    ADD CONSTRAINT challenges_rewards_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.challenges_rewards
    ADD CONSTRAINT challenges_rewards_challenge_id_challenge_difficulty_id_key UNIQUE (challenge_id, challenge_difficulty_id);

ALTER TABLE ONLY public.challenges_tasks_set
    ADD CONSTRAINT challenges_tasks_set_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.challenges_user_layout
    ADD CONSTRAINT challenges_user_layout_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.challenges_user_layout
    ADD CONSTRAINT challenges_user_layout_user_id_challenge_id_key UNIQUE (user_id, challenge_id);

ALTER TABLE ONLY public.user_challenges
    ADD CONSTRAINT user_challenges_pkey PRIMARY KEY (id);

-- ============================================================
-- INDEXES
-- ============================================================

-- Уникальный индекс: один пользователь может иметь только один набор заданий в статусах draft/in_progress/completed
CREATE UNIQUE INDEX challenges_tasks_set_user_id_idx 
    ON public.challenges_tasks_set USING btree (user_id) 
    WHERE (status = ANY (ARRAY[1, 2, 3]));

-- Уникальный индекс: в одном наборе заданий не может быть дубликатов челленджей (в слотах 1-4)
CREATE UNIQUE INDEX user_challenges_task_set_id_challenge_id_idx 
    ON public.user_challenges USING btree (task_set_id, challenge_id) 
    WHERE ((slot >= 1) AND (slot <= 4));

-- ============================================================
-- FOREIGN KEY constraints
-- ============================================================

-- challenges -> challenges_categories
ALTER TABLE ONLY public.challenges
    ADD CONSTRAINT challenges_category_id_fkey 
    FOREIGN KEY (category_id) 
    REFERENCES public.challenges_categories(id) 
    ON DELETE CASCADE;

-- challenges_rewards -> challenges
ALTER TABLE ONLY public.challenges_rewards
    ADD CONSTRAINT challenges_rewards_challenge_id_fkey 
    FOREIGN KEY (challenge_id) 
    REFERENCES public.challenges(id) 
    ON DELETE CASCADE;

-- challenges_rewards -> challenges_difficulties
ALTER TABLE ONLY public.challenges_rewards
    ADD CONSTRAINT challenges_rewards_challenge_difficulty_id_fkey 
    FOREIGN KEY (challenge_difficulty_id) 
    REFERENCES public.challenges_difficulties(id) 
    ON DELETE CASCADE;

-- challenges_tasks_set -> users
ALTER TABLE ONLY public.challenges_tasks_set
    ADD CONSTRAINT challenges_tasks_set_user_id_fkey 
    FOREIGN KEY (user_id) 
    REFERENCES public.users(user_id) 
    ON DELETE CASCADE;

-- challenges_tasks_set -> tasks_set_statuses
ALTER TABLE ONLY public.challenges_tasks_set
    ADD CONSTRAINT challenges_tasks_set_status_fkey 
    FOREIGN KEY (status) 
    REFERENCES public.tasks_set_statuses(id) 
    ON DELETE RESTRICT;

-- challenges_user_layout -> users
ALTER TABLE ONLY public.challenges_user_layout
    ADD CONSTRAINT challenges_user_layout_user_id_fkey 
    FOREIGN KEY (user_id) 
    REFERENCES public.users(user_id) 
    ON DELETE CASCADE;

-- challenges_user_layout -> challenges
ALTER TABLE ONLY public.challenges_user_layout
    ADD CONSTRAINT challenges_user_layout_challenge_id_fkey 
    FOREIGN KEY (challenge_id) 
    REFERENCES public.challenges(id) 
    ON DELETE CASCADE;

-- user_challenges -> challenges_tasks_set
ALTER TABLE ONLY public.user_challenges
    ADD CONSTRAINT user_challenges_task_set_id_fkey 
    FOREIGN KEY (task_set_id) 
    REFERENCES public.challenges_tasks_set(id) 
    ON DELETE CASCADE;

-- user_challenges -> challenges
ALTER TABLE ONLY public.user_challenges
    ADD CONSTRAINT user_challenges_challenge_id_fkey 
    FOREIGN KEY (challenge_id) 
    REFERENCES public.challenges(id) 
    ON DELETE CASCADE;

-- user_challenges -> challenges_difficulties
ALTER TABLE ONLY public.user_challenges
    ADD CONSTRAINT user_challenges_challenge_difficulty_id_fkey 
    FOREIGN KEY (challenge_difficulty_id) 
    REFERENCES public.challenges_difficulties(id) 
    ON DELETE RESTRICT;

-- user_challenges -> user_challenges_statuses
ALTER TABLE ONLY public.user_challenges
    ADD CONSTRAINT user_challenges_status_fkey 
    FOREIGN KEY (status) 
    REFERENCES public.user_challenges_statuses(id) 
    ON DELETE RESTRICT;
