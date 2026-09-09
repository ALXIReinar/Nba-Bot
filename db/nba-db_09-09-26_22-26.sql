--
-- PostgreSQL database dump
--

\restrict 1M6bO7QXk7OHFmE3b8XydLcrckzsnhqQy6wtf3TWNWwTtIwAdh3y4zblDkEz9gM

-- Dumped from database version 16.10
-- Dumped by pg_dump version 16.10

-- Started on 2026-09-09 22:26:19

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 215 (class 1259 OID 2673506)
-- Name: cards; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cards (
    card_id integer NOT NULL,
    name character varying(50) NOT NULL,
    "position" character varying(8) NOT NULL,
    club character varying(50) NOT NULL,
    category character varying(8) NOT NULL,
    mid_range_shot integer,
    threepoint_shot integer,
    layup integer,
    dunk integer,
    perimetr_defense integer,
    interior_defense integer,
    dribbling integer,
    passplay integer,
    block integer,
    hands integer,
    pass_perception integer,
    steal integer,
    active boolean
);


ALTER TABLE public.cards OWNER TO postgres;

--
-- TOC entry 217 (class 1259 OID 2673516)
-- Name: cards_card_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.cards ALTER COLUMN card_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.cards_card_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 216 (class 1259 OID 2673511)
-- Name: user_team; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.user_team (
    user_id bigint NOT NULL,
    pg integer,
    sf integer,
    c integer,
    sg integer,
    pf integer
);


ALTER TABLE public.user_team OWNER TO postgres;

--
-- TOC entry 4888 (class 0 OID 2673506)
-- Dependencies: 215
-- Data for Name: cards; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.cards (card_id, name, "position", club, category, mid_range_shot, threepoint_shot, layup, dunk, perimetr_defense, interior_defense, dribbling, passplay, block, hands, pass_perception, steal, active) FROM stdin;
\.


--
-- TOC entry 4889 (class 0 OID 2673511)
-- Dependencies: 216
-- Data for Name: user_team; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.user_team (user_id, pg, sf, c, sg, pf) FROM stdin;
\.


--
-- TOC entry 4896 (class 0 OID 0)
-- Dependencies: 217
-- Name: cards_card_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.cards_card_id_seq', 1, false);


--
-- TOC entry 4740 (class 2606 OID 2673510)
-- Name: cards cards_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cards
    ADD CONSTRAINT cards_pkey PRIMARY KEY (card_id);


--
-- TOC entry 4742 (class 2606 OID 2673518)
-- Name: user_team user_team_pg_sf_c_sg_pf_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_team
    ADD CONSTRAINT user_team_pg_sf_c_sg_pf_key UNIQUE (pg, sf, c, sg, pf);


--
-- TOC entry 4744 (class 2606 OID 2673515)
-- Name: user_team user_team_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.user_team
    ADD CONSTRAINT user_team_pkey PRIMARY KEY (user_id);


-- Completed on 2026-09-09 22:26:19

--
-- PostgreSQL database dump complete
--

\unrestrict 1M6bO7QXk7OHFmE3b8XydLcrckzsnhqQy6wtf3TWNWwTtIwAdh3y4zblDkEz9gM

