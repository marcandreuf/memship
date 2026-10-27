--
-- PostgreSQL database dump
--

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

--
-- Name: party_sync_display_name_from_person(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.party_sync_display_name_from_person() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    UPDATE party
    SET display_name = btrim(coalesce(NEW.first_name, '') || ' ' || coalesce(NEW.last_name, '')),
        updated_at = now()
    WHERE id = NEW.party_id
      AND btrim(coalesce(NEW.first_name, '') || ' ' || coalesce(NEW.last_name, '')) <> '';
    RETURN NULL;
END;
$$;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: activities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.activities (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    slug character varying(150) NOT NULL,
    description text,
    short_description character varying(500),
    starts_at timestamp with time zone NOT NULL,
    ends_at timestamp with time zone NOT NULL,
    location character varying(255),
    location_details text,
    location_url character varying(500),
    registration_starts_at timestamp with time zone NOT NULL,
    registration_ends_at timestamp with time zone NOT NULL,
    min_participants integer,
    max_participants integer NOT NULL,
    current_participants integer,
    waitlist_count integer,
    min_age integer,
    max_age integer,
    allowed_membership_types integer[],
    status character varying(20),
    tax_rate numeric(5,2),
    image_url character varying(500),
    thumbnail_url character varying(500),
    features jsonb,
    registration_fields_schema jsonb,
    requirements text,
    what_to_bring text,
    cancellation_policy text,
    allow_self_cancellation boolean,
    self_cancellation_deadline_hours integer,
    is_active boolean,
    is_featured boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    created_by integer,
    CONSTRAINT activity_slug_format CHECK (((slug)::text ~ '^[a-z0-9-]+$'::text)),
    CONSTRAINT valid_status CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'published'::character varying, 'cancelled'::character varying, 'completed'::character varying, 'archived'::character varying])::text[])))
);

--
-- Name: activities_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.activities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: activities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.activities_id_seq OWNED BY public.activities.id;

--
-- Name: activity_attachment_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.activity_attachment_types (
    id integer NOT NULL,
    activity_id integer NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    allowed_extensions character varying[],
    max_file_size_mb integer DEFAULT 5,
    is_mandatory boolean DEFAULT true,
    display_order integer DEFAULT 1,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

--
-- Name: activity_attachment_types_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.activity_attachment_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: activity_attachment_types_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.activity_attachment_types_id_seq OWNED BY public.activity_attachment_types.id;

--
-- Name: activity_consents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.activity_consents (
    id integer NOT NULL,
    activity_id integer NOT NULL,
    title character varying(255) NOT NULL,
    content text NOT NULL,
    is_mandatory boolean DEFAULT true,
    display_order integer DEFAULT 1,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

--
-- Name: activity_consents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.activity_consents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: activity_consents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.activity_consents_id_seq OWNED BY public.activity_consents.id;

--
-- Name: activity_modalities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.activity_modalities (
    id integer NOT NULL,
    activity_id integer NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    max_participants integer,
    current_participants integer,
    registration_deadline timestamp with time zone,
    display_order integer,
    is_active boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

--
-- Name: activity_modalities_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.activity_modalities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: activity_modalities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.activity_modalities_id_seq OWNED BY public.activity_modalities.id;

--
-- Name: activity_prices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.activity_prices (
    id integer NOT NULL,
    activity_id integer NOT NULL,
    modality_id integer,
    name character varying(255) NOT NULL,
    description text,
    amount numeric(10,2) NOT NULL,
    display_order integer,
    is_optional boolean,
    is_default boolean,
    is_visible boolean,
    max_registrations integer,
    current_registrations integer,
    valid_from timestamp with time zone,
    valid_until timestamp with time zone,
    is_active boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT activity_price_amount_non_negative CHECK ((amount >= (0)::numeric))
);

--
-- Name: activity_prices_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.activity_prices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: activity_prices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.activity_prices_id_seq OWNED BY public.activity_prices.id;

--
-- Name: addresses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.addresses (
    id integer NOT NULL,
    address_line1 character varying(255) NOT NULL,
    address_line2 character varying(255),
    city character varying(100) NOT NULL,
    state_province character varying(100),
    postal_code character varying(20),
    country character varying(3),
    latitude numeric(10,7),
    longitude numeric(10,7),
    is_primary boolean,
    display_order integer,
    label character varying(100),
    is_active boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    party_id bigint,
    space_id integer,
    CONSTRAINT addresses_exactly_one_owner CHECK ((num_nonnulls(party_id, space_id) = 1))
);

--
-- Name: addresses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.addresses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: addresses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.addresses_id_seq OWNED BY public.addresses.id;

--
-- Name: announcement_recipients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.announcement_recipients (
    id integer NOT NULL,
    announcement_id integer NOT NULL,
    member_id integer NOT NULL,
    user_id integer,
    email_eligible boolean NOT NULL,
    in_app boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    email_sent boolean
);

--
-- Name: announcement_recipients_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.announcement_recipients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: announcement_recipients_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.announcement_recipients_id_seq OWNED BY public.announcement_recipients.id;

--
-- Name: announcements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.announcements (
    id integer NOT NULL,
    subject character varying(200) NOT NULL,
    body text NOT NULL,
    target_type character varying(20) NOT NULL,
    target_id integer,
    status character varying(20) NOT NULL,
    recipient_count integer,
    sent_at timestamp with time zone,
    created_by_user_id integer NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT valid_announcement_status CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'sent'::character varying])::text[]))),
    CONSTRAINT valid_announcement_target_type CHECK (((target_type)::text = ANY ((ARRAY['all'::character varying, 'group'::character varying, 'membership_type'::character varying])::text[])))
);

--
-- Name: announcements_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.announcements_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: announcements_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.announcements_id_seq OWNED BY public.announcements.id;

--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    id integer NOT NULL,
    table_name character varying(100) NOT NULL,
    record_id integer NOT NULL,
    action character varying(50) NOT NULL,
    user_id integer,
    old_values jsonb,
    new_values jsonb,
    changed_fields text[],
    ip_address inet,
    user_agent text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT valid_action CHECK (((action)::text = ANY ((ARRAY['create'::character varying, 'update'::character varying, 'delete'::character varying])::text[])))
);

--
-- Name: audit_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: audit_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_logs_id_seq OWNED BY public.audit_logs.id;

--
-- Name: billing_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.billing_runs (
    id integer NOT NULL,
    frequency character varying(20) NOT NULL,
    period_start date NOT NULL,
    period_end date NOT NULL,
    triggered_by character varying(20) NOT NULL,
    triggered_by_user_id integer,
    status character varying(20) NOT NULL,
    receipts_generated integer NOT NULL,
    errors jsonb NOT NULL,
    started_at timestamp with time zone DEFAULT now(),
    finished_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT valid_billing_run_frequency CHECK (((frequency)::text = ANY ((ARRAY['monthly'::character varying, 'quarterly'::character varying, 'annual'::character varying])::text[]))),
    CONSTRAINT valid_billing_run_status CHECK (((status)::text = ANY ((ARRAY['success'::character varying, 'failed'::character varying, 'partial_failure'::character varying])::text[]))),
    CONSTRAINT valid_billing_run_triggered_by CHECK (((triggered_by)::text = ANY ((ARRAY['scheduled'::character varying, 'manual'::character varying])::text[])))
);

--
-- Name: billing_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.billing_runs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: billing_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.billing_runs_id_seq OWNED BY public.billing_runs.id;

--
-- Name: bookings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bookings (
    id integer NOT NULL,
    space_slot_id integer NOT NULL,
    party_id bigint NOT NULL,
    status character varying(20) DEFAULT 'booked'::character varying NOT NULL,
    waitlisted_at timestamp with time zone,
    cancelled_at timestamp with time zone,
    cancelled_by_user_id integer,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT booking_status_valid CHECK (((status)::text = ANY ((ARRAY['booked'::character varying, 'waitlisted'::character varying, 'cancelled'::character varying])::text[])))
);

--
-- Name: bookings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bookings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: bookings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bookings_id_seq OWNED BY public.bookings.id;

--
-- Name: concepts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.concepts (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    code character varying(50),
    description text,
    concept_type character varying(20) NOT NULL,
    default_amount numeric(10,2) NOT NULL,
    vat_rate numeric(5,2) NOT NULL,
    default_discount numeric(10,2),
    default_discount_type character varying(20),
    accounting_code character varying(50),
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT concept_amount_non_negative CHECK ((default_amount >= (0)::numeric)),
    CONSTRAINT concept_vat_rate_range CHECK (((vat_rate >= (0)::numeric) AND (vat_rate <= (100)::numeric))),
    CONSTRAINT valid_concept_type CHECK (((concept_type)::text = ANY ((ARRAY['membership'::character varying, 'activity'::character varying, 'booking'::character varying, 'manual'::character varying, 'service'::character varying])::text[]))),
    CONSTRAINT valid_discount_type CHECK ((((default_discount_type)::text = ANY ((ARRAY['percentage'::character varying, 'fixed'::character varying])::text[])) OR (default_discount_type IS NULL)))
);

--
-- Name: concepts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.concepts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: concepts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.concepts_id_seq OWNED BY public.concepts.id;

--
-- Name: contact_channels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contact_channels (
    code text NOT NULL,
    name text NOT NULL
);

--
-- Name: contact_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contact_types (
    id integer NOT NULL,
    code character varying(20) NOT NULL,
    name character varying(50) NOT NULL,
    description character varying(255),
    is_active boolean,
    display_order integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    channel text NOT NULL
);

--
-- Name: contact_types_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.contact_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: contact_types_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contact_types_id_seq OWNED BY public.contact_types.id;

--
-- Name: contacts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.contacts (
    id integer NOT NULL,
    contact_type_id integer,
    value character varying(255) NOT NULL,
    label character varying(100),
    is_primary boolean,
    display_order integer,
    is_active boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    party_id bigint NOT NULL,
    channel text,
    CONSTRAINT contacts_channel_iff_type CHECK (((contact_type_id IS NULL) = (channel IS NULL)))
);

--
-- Name: contacts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.contacts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: contacts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.contacts_id_seq OWNED BY public.contacts.id;

--
-- Name: custom_field_definitions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.custom_field_definitions (
    id integer NOT NULL,
    key character varying(50) NOT NULL,
    field_type character varying(20) NOT NULL,
    label character varying(100) NOT NULL,
    labels jsonb DEFAULT '{}'::jsonb NOT NULL,
    help_text character varying(255),
    options jsonb,
    required boolean DEFAULT false NOT NULL,
    member_access character varying(10) DEFAULT 'read'::character varying NOT NULL,
    admin_access character varying(10) DEFAULT 'write'::character varying NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT valid_custom_field_admin_access CHECK (((admin_access)::text = ANY ((ARRAY['read'::character varying, 'write'::character varying])::text[]))),
    CONSTRAINT valid_custom_field_member_access CHECK (((member_access)::text = ANY ((ARRAY['hidden'::character varying, 'read'::character varying, 'write'::character varying])::text[]))),
    CONSTRAINT valid_custom_field_type CHECK (((field_type)::text = ANY ((ARRAY['text'::character varying, 'textarea'::character varying, 'number'::character varying, 'date'::character varying, 'boolean'::character varying, 'select'::character varying])::text[])))
);

--
-- Name: custom_field_definitions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.custom_field_definitions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: custom_field_definitions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.custom_field_definitions_id_seq OWNED BY public.custom_field_definitions.id;

--
-- Name: custom_field_values; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.custom_field_values (
    id integer NOT NULL,
    definition_id integer NOT NULL,
    party_id bigint NOT NULL,
    value text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

--
-- Name: custom_field_values_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.custom_field_values_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: custom_field_values_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.custom_field_values_id_seq OWNED BY public.custom_field_values.id;

--
-- Name: discount_codes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.discount_codes (
    id integer NOT NULL,
    activity_id integer NOT NULL,
    code character varying(50) NOT NULL,
    description text,
    discount_type character varying(20) NOT NULL,
    discount_value numeric(10,2) NOT NULL,
    max_uses integer,
    current_uses integer DEFAULT 0,
    valid_from timestamp with time zone,
    valid_until timestamp with time zone,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT discount_value_positive CHECK ((discount_value > (0)::numeric)),
    CONSTRAINT percentage_max_100 CHECK ((((discount_type)::text <> 'percentage'::text) OR (discount_value <= (100)::numeric))),
    CONSTRAINT valid_discount_type CHECK (((discount_type)::text = ANY ((ARRAY['percentage'::character varying, 'fixed'::character varying])::text[])))
);

--
-- Name: discount_codes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.discount_codes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: discount_codes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.discount_codes_id_seq OWNED BY public.discount_codes.id;

--
-- Name: groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.groups (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    slug character varying(100) NOT NULL,
    description text,
    is_billable boolean,
    display_order integer,
    color character varying(7),
    icon character varying(50),
    is_active boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT group_slug_format CHECK (((slug)::text ~ '^[a-z0-9-]+$'::text))
);

--
-- Name: groups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.groups_id_seq OWNED BY public.groups.id;

--
-- Name: invoice_sequences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invoice_sequences (
    year integer NOT NULL,
    next_number integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);

--
-- Name: mail_transport_health; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mail_transport_health (
    provider character varying(20) NOT NULL,
    fingerprint character varying(64) NOT NULL,
    last_success_at timestamp with time zone,
    last_failure_at timestamp with time zone,
    last_failure character varying(40),
    updated_at timestamp with time zone DEFAULT now()
);

--
-- Name: members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.members (
    id integer NOT NULL,
    party_id bigint NOT NULL,
    membership_type_id integer,
    member_number character varying(50),
    status character varying(50),
    status_reason text,
    status_changed_at timestamp with time zone DEFAULT now(),
    joined_at date DEFAULT CURRENT_DATE NOT NULL,
    expires_at date,
    renewed_at date,
    guardian_party_id bigint,
    is_minor boolean,
    communication_preferences jsonb,
    internal_notes text,
    is_active boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    created_by integer,
    membership_reverted_from_id integer,
    membership_reverted_at timestamp with time zone,
    CONSTRAINT valid_status CHECK (((status)::text = ANY ((ARRAY['pending'::character varying, 'active'::character varying, 'suspended'::character varying, 'cancelled'::character varying, 'expired'::character varying])::text[])))
);

--
-- Name: members_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.members_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: members_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.members_id_seq OWNED BY public.members.id;

--
-- Name: membership_types; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.membership_types (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    slug character varying(100) NOT NULL,
    min_age integer,
    max_age integer,
    max_members integer,
    current_members integer,
    base_price numeric(10,2),
    billing_frequency character varying(20),
    is_fixed_term boolean,
    term_months integer,
    benefits text[],
    display_order integer,
    color character varying(7),
    is_active boolean,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    group_id integer,
    is_default boolean DEFAULT false NOT NULL,
    CONSTRAINT default_membership_type_is_free CHECK (((NOT is_default) OR (COALESCE(base_price, (0)::numeric) = (0)::numeric))),
    CONSTRAINT membership_type_slug_format CHECK (((slug)::text ~ '^[a-z0-9-]+$'::text)),
    CONSTRAINT valid_billing_frequency CHECK (((billing_frequency)::text = ANY ((ARRAY['monthly'::character varying, 'quarterly'::character varying, 'annual'::character varying, 'one_time'::character varying])::text[])))
);

--
-- Name: membership_types_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.membership_types_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: membership_types_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.membership_types_id_seq OWNED BY public.membership_types.id;

--
-- Name: notifications; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications (
    id integer NOT NULL,
    user_id integer NOT NULL,
    source_type character varying(30) NOT NULL,
    source_id integer NOT NULL,
    title character varying(200) NOT NULL,
    excerpt character varying(280),
    read_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT valid_notification_source_type CHECK (((source_type)::text = 'announcement'::text))
);

--
-- Name: notifications_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.notifications_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: notifications_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.notifications_id_seq OWNED BY public.notifications.id;

--
-- Name: organization_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.organization_settings (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    legal_name character varying(255),
    email character varying(255),
    phone character varying(50),
    website character varying(255),
    logo_url character varying(500),
    tax_id character varying(50),
    locale character varying(10),
    timezone character varying(50),
    currency character varying(3),
    date_format character varying(20),
    brand_color character varying(7),
    features jsonb,
    custom_settings jsonb,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    bank_name character varying(255),
    bank_iban character varying(34),
    bank_bic character varying(11),
    invoice_prefix character varying(10) DEFAULT 'INV'::character varying,
    invoice_next_number integer DEFAULT 1,
    invoice_annual_reset boolean,
    default_vat_rate numeric(5,2),
    creditor_id character varying(35),
    sepa_format character varying(20),
    member_number_prefix character varying(20) DEFAULT ''::character varying NOT NULL,
    member_number_padding smallint DEFAULT '4'::smallint NOT NULL,
    member_number_next integer DEFAULT 1 NOT NULL,
    sso_config jsonb DEFAULT '{}'::jsonb NOT NULL,
    mailing_config jsonb DEFAULT '{}'::jsonb NOT NULL,
    communications_config jsonb DEFAULT '{}'::jsonb NOT NULL,
    party_id bigint NOT NULL,
    CONSTRAINT single_organization CHECK ((id = 1))
);

--
-- Name: organization_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.organization_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: organization_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.organization_settings_id_seq OWNED BY public.organization_settings.id;

--
-- Name: party; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.party (
    id bigint NOT NULL,
    kind text NOT NULL,
    display_name text NOT NULL,
    national_id character varying(50),
    email character varying(255),
    photo_url character varying(500),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

--
-- Name: party_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.party_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: party_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.party_id_seq OWNED BY public.party.id;

--
-- Name: party_kinds; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.party_kinds (
    code text NOT NULL,
    name text NOT NULL,
    is_natural boolean DEFAULT false NOT NULL,
    display_order integer DEFAULT 0 NOT NULL
);

--
-- Name: payment_providers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payment_providers (
    id integer NOT NULL,
    provider_type character varying(50) NOT NULL,
    display_name character varying(255) NOT NULL,
    status character varying(20) NOT NULL,
    config jsonb,
    is_default boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT valid_provider_status CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'test'::character varying, 'disabled'::character varying])::text[])))
);

--
-- Name: payment_providers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payment_providers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: payment_providers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payment_providers_id_seq OWNED BY public.payment_providers.id;

--
-- Name: persons; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.persons (
    first_name character varying(100) NOT NULL,
    last_name character varying(100) NOT NULL,
    date_of_birth date,
    gender character varying(20),
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    bank_iban character varying(34),
    bank_bic character varying(11),
    bank_holder_name character varying(255),
    payment_method character varying(20),
    stripe_customer_id character varying(255),
    party_id bigint NOT NULL,
    kind text DEFAULT 'person'::text NOT NULL,
    CONSTRAINT persons_kind_check CHECK ((kind = 'person'::text))
);

--
-- Name: receipt_reminders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.receipt_reminders (
    id integer NOT NULL,
    receipt_id integer NOT NULL,
    reminder_number integer NOT NULL,
    channel character varying(20) NOT NULL,
    status character varying(20) NOT NULL,
    to_email character varying(255),
    triggered_by character varying(20) NOT NULL,
    triggered_by_user_id integer,
    error text,
    sent_at timestamp with time zone DEFAULT now(),
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT valid_receipt_reminder_channel CHECK (((channel)::text = 'email'::text)),
    CONSTRAINT valid_receipt_reminder_status CHECK (((status)::text = ANY ((ARRAY['queued'::character varying, 'sent'::character varying, 'failed'::character varying, 'skipped'::character varying])::text[]))),
    CONSTRAINT valid_receipt_reminder_triggered_by CHECK (((triggered_by)::text = ANY ((ARRAY['scheduled'::character varying, 'manual'::character varying])::text[])))
);

--
-- Name: receipt_reminders_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.receipt_reminders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: receipt_reminders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.receipt_reminders_id_seq OWNED BY public.receipt_reminders.id;

--
-- Name: receipts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.receipts (
    id integer NOT NULL,
    receipt_number character varying(50) NOT NULL,
    party_id bigint NOT NULL,
    concept_id integer,
    registration_id integer,
    remittance_id integer,
    created_by integer,
    origin character varying(20) NOT NULL,
    description character varying(500) NOT NULL,
    base_amount numeric(10,2) NOT NULL,
    vat_rate numeric(5,2) NOT NULL,
    vat_amount numeric(10,2) NOT NULL,
    total_amount numeric(10,2) NOT NULL,
    discount_amount numeric(10,2),
    discount_type character varying(20),
    status character varying(20) NOT NULL,
    payment_method character varying(20),
    emission_date date NOT NULL,
    due_date date,
    payment_date date,
    return_date date,
    return_reason character varying(255),
    is_batchable boolean NOT NULL,
    transaction_id character varying(255),
    billing_period_start date,
    billing_period_end date,
    notes text,
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    stripe_checkout_session_id character varying(255),
    stripe_payment_intent_id character varying(255),
    refund_amount numeric(10,2),
    refund_date date,
    refund_reason character varying(255),
    redsys_ds_order character varying(12),
    redsys_auth_code character varying(8),
    booking_id integer,
    purchased_membership_type_id integer,
    document_type character varying(20) DEFAULT 'invoice'::character varying NOT NULL,
    rectifies_receipt_id integer,
    CONSTRAINT credit_note_rectifies_a_receipt CHECK (((((document_type)::text = 'invoice'::text) AND (rectifies_receipt_id IS NULL)) OR (((document_type)::text = 'credit_note'::text) AND (rectifies_receipt_id IS NOT NULL)))),
    CONSTRAINT receipt_base_sign_matches_document_type CHECK (((((document_type)::text = 'invoice'::text) AND (base_amount >= (0)::numeric)) OR (((document_type)::text = 'credit_note'::text) AND (base_amount <= (0)::numeric)))),
    CONSTRAINT receipt_total_sign_matches_document_type CHECK (((((document_type)::text = 'invoice'::text) AND (total_amount >= (0)::numeric)) OR (((document_type)::text = 'credit_note'::text) AND (total_amount <= (0)::numeric)))),
    CONSTRAINT receipt_vat_range CHECK (((vat_rate >= (0)::numeric) AND (vat_rate <= (100)::numeric))),
    CONSTRAINT valid_payment_method CHECK ((((payment_method)::text = ANY ((ARRAY['cash'::character varying, 'bank_transfer'::character varying, 'card'::character varying, 'direct_debit'::character varying, 'stripe_checkout'::character varying, 'redsys'::character varying, 'bizum'::character varying])::text[])) OR (payment_method IS NULL))),
    CONSTRAINT valid_receipt_discount_type CHECK ((((discount_type)::text = ANY ((ARRAY['percentage'::character varying, 'fixed'::character varying])::text[])) OR (discount_type IS NULL))),
    CONSTRAINT valid_receipt_document_type CHECK (((document_type)::text = ANY ((ARRAY['invoice'::character varying, 'credit_note'::character varying])::text[]))),
    CONSTRAINT valid_receipt_origin CHECK (((origin)::text = ANY ((ARRAY['membership'::character varying, 'activity'::character varying, 'booking'::character varying, 'manual'::character varying, 'service'::character varying])::text[]))),
    CONSTRAINT valid_receipt_status CHECK (((status)::text = ANY ((ARRAY['new'::character varying, 'pending'::character varying, 'emitted'::character varying, 'paid'::character varying, 'returned'::character varying, 'cancelled'::character varying, 'overdue'::character varying])::text[])))
);

--
-- Name: receipts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.receipts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: receipts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.receipts_id_seq OWNED BY public.receipts.id;

--
-- Name: registration_attachments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.registration_attachments (
    id integer NOT NULL,
    registration_id integer NOT NULL,
    attachment_type_id integer,
    file_name character varying(255) NOT NULL,
    file_path character varying(500) NOT NULL,
    file_size integer,
    mime_type character varying(100),
    uploaded_at timestamp with time zone DEFAULT now()
);

--
-- Name: registration_attachments_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.registration_attachments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: registration_attachments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.registration_attachments_id_seq OWNED BY public.registration_attachments.id;

--
-- Name: registration_consents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.registration_consents (
    id integer NOT NULL,
    registration_id integer NOT NULL,
    activity_consent_id integer NOT NULL,
    accepted boolean DEFAULT true NOT NULL,
    accepted_at timestamp with time zone DEFAULT now()
);

--
-- Name: registration_consents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.registration_consents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: registration_consents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.registration_consents_id_seq OWNED BY public.registration_consents.id;

--
-- Name: registrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.registrations (
    id integer NOT NULL,
    activity_id integer NOT NULL,
    party_id bigint NOT NULL,
    modality_id integer,
    price_id integer,
    status character varying(20) DEFAULT 'confirmed'::character varying NOT NULL,
    registration_data jsonb DEFAULT '{}'::jsonb,
    member_notes text,
    admin_notes text,
    cancelled_at timestamp with time zone,
    cancelled_by integer,
    cancelled_reason text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    discount_code_id integer,
    original_amount numeric(10,2),
    discounted_amount numeric(10,2),
    CONSTRAINT valid_registration_status CHECK (((status)::text = ANY ((ARRAY['confirmed'::character varying, 'waitlist'::character varying, 'cancelled'::character varying, 'pending'::character varying])::text[])))
);

--
-- Name: registrations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.registrations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: registrations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.registrations_id_seq OWNED BY public.registrations.id;

--
-- Name: reminders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reminders (
    id integer NOT NULL,
    content text NOT NULL,
    due_date date,
    is_done boolean DEFAULT false NOT NULL,
    created_by integer,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

--
-- Name: reminders_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.reminders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: reminders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.reminders_id_seq OWNED BY public.reminders.id;

--
-- Name: remittance_receipts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.remittance_receipts (
    id integer NOT NULL,
    remittance_id integer NOT NULL,
    receipt_id integer NOT NULL,
    amount_sent numeric(10,2) NOT NULL,
    released_at timestamp with time zone,
    release_reason character varying(30),
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT remittance_receipt_amount_non_negative CHECK ((amount_sent >= (0)::numeric)),
    CONSTRAINT valid_release_reason CHECK (((release_reason IS NULL) OR ((release_reason)::text = ANY ((ARRAY['reemitted'::character varying, 'cancelled'::character varying, 'paid_by_other_means'::character varying, 'batch_cancelled'::character varying])::text[]))))
);

--
-- Name: remittance_receipts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.remittance_receipts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: remittance_receipts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.remittance_receipts_id_seq OWNED BY public.remittance_receipts.id;

--
-- Name: remittance_sequences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.remittance_sequences (
    year integer NOT NULL,
    next_number integer DEFAULT 1 NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone
);

--
-- Name: remittances; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.remittances (
    id integer NOT NULL,
    remittance_number character varying(50) NOT NULL,
    remittance_type character varying(20) NOT NULL,
    status character varying(20) NOT NULL,
    emission_date date NOT NULL,
    due_date date NOT NULL,
    total_amount numeric(12,2) NOT NULL,
    receipt_count integer NOT NULL,
    sepa_file_path character varying(500),
    creditor_name character varying(255) NOT NULL,
    creditor_iban character varying(34) NOT NULL,
    creditor_bic character varying(11),
    creditor_id character varying(35) NOT NULL,
    notes text,
    created_by integer,
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT remittance_total_non_negative CHECK ((total_amount >= (0)::numeric)),
    CONSTRAINT valid_remittance_status CHECK (((status)::text = ANY ((ARRAY['draft'::character varying, 'ready'::character varying, 'submitted'::character varying, 'processed'::character varying, 'closed'::character varying, 'cancelled'::character varying])::text[]))),
    CONSTRAINT valid_remittance_type CHECK (((remittance_type)::text = 'sepa'::text))
);

--
-- Name: remittances_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.remittances_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: remittances_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.remittances_id_seq OWNED BY public.remittances.id;

--
-- Name: role_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.role_permissions (
    role_id integer NOT NULL,
    permission_key character varying(64) NOT NULL
);

--
-- Name: roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.roles (
    id integer NOT NULL,
    slug character varying(50) NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    is_system boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

--
-- Name: roles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.roles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: roles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.roles_id_seq OWNED BY public.roles.id;

--
-- Name: sepa_mandates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sepa_mandates (
    id integer NOT NULL,
    party_id bigint NOT NULL,
    mandate_reference character varying(35) NOT NULL,
    creditor_id character varying(35) NOT NULL,
    debtor_name character varying(255) NOT NULL,
    debtor_iban character varying(34) NOT NULL,
    debtor_bic character varying(11),
    mandate_type character varying(20) NOT NULL,
    signature_method character varying(20) NOT NULL,
    status character varying(20) NOT NULL,
    signed_at date NOT NULL,
    document_path character varying(500),
    cancelled_at timestamp with time zone,
    notes text,
    is_active boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT valid_mandate_status CHECK (((status)::text = ANY ((ARRAY['active'::character varying, 'cancelled'::character varying, 'expired'::character varying])::text[]))),
    CONSTRAINT valid_mandate_type CHECK (((mandate_type)::text = ANY ((ARRAY['recurrent'::character varying, 'one_off'::character varying])::text[]))),
    CONSTRAINT valid_signature_method CHECK (((signature_method)::text = ANY ((ARRAY['paper'::character varying, 'digital'::character varying])::text[])))
);

--
-- Name: sepa_mandates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.sepa_mandates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: sepa_mandates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.sepa_mandates_id_seq OWNED BY public.sepa_mandates.id;

--
-- Name: space_slots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.space_slots (
    id integer NOT NULL,
    space_id integer NOT NULL,
    slot_date date NOT NULL,
    start_time time without time zone NOT NULL,
    end_time time without time zone NOT NULL,
    capacity smallint DEFAULT '1'::smallint NOT NULL,
    series_id uuid,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    price numeric(10,2),
    CONSTRAINT space_slot_capacity_valid CHECK ((capacity >= 1)),
    CONSTRAINT space_slot_price_non_negative CHECK (((price IS NULL) OR (price >= (0)::numeric))),
    CONSTRAINT space_slot_time_valid CHECK ((end_time > start_time))
);

--
-- Name: space_slots_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.space_slots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: space_slots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.space_slots_id_seq OWNED BY public.space_slots.id;

--
-- Name: spaces; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.spaces (
    id integer NOT NULL,
    name character varying(200) NOT NULL,
    space_type character varying(50),
    description text,
    open_time time without time zone NOT NULL,
    close_time time without time zone NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    allowed_membership_types integer[],
    price numeric(10,2),
    CONSTRAINT space_hours_valid CHECK ((close_time > open_time)),
    CONSTRAINT space_price_non_negative CHECK (((price IS NULL) OR (price >= (0)::numeric)))
);

--
-- Name: spaces_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.spaces_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: spaces_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.spaces_id_seq OWNED BY public.spaces.id;

--
-- Name: user_identities; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_identities (
    id integer NOT NULL,
    user_id integer NOT NULL,
    provider character varying(20) NOT NULL,
    provider_subject character varying(255) NOT NULL,
    email character varying(255),
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT valid_auth_provider CHECK (((provider)::text = ANY ((ARRAY['google'::character varying, 'apple'::character varying])::text[])))
);

--
-- Name: user_identities_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_identities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: user_identities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_identities_id_seq OWNED BY public.user_identities.id;

--
-- Name: user_roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_roles (
    user_id integer NOT NULL,
    role_id integer NOT NULL,
    assigned_at timestamp with time zone DEFAULT now(),
    assigned_by integer
);

--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    id integer NOT NULL,
    party_id bigint NOT NULL,
    email character varying(255) NOT NULL,
    password_hash character varying(255),
    email_verified boolean,
    email_verified_at timestamp with time zone,
    last_login_at timestamp with time zone,
    last_login_ip inet,
    reset_token character varying(255),
    reset_token_expires_at timestamp with time zone,
    is_active boolean,
    is_locked boolean,
    locked_at timestamp with time zone,
    locked_reason text,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    verification_token character varying(255),
    verification_token_expires_at timestamp with time zone,
    sessions_valid_from timestamp with time zone
);

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;

--
-- Name: webhook_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.webhook_events (
    id integer NOT NULL,
    provider_type character varying(50) NOT NULL,
    external_event_id character varying(255) NOT NULL,
    event_type character varying(100) NOT NULL,
    payload jsonb NOT NULL,
    status character varying(20) NOT NULL,
    error_message text,
    receipt_id integer,
    processed_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT valid_webhook_event_status CHECK (((status)::text = ANY ((ARRAY['received'::character varying, 'processed'::character varying, 'failed'::character varying, 'ignored'::character varying])::text[])))
);

--
-- Name: webhook_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.webhook_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: webhook_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.webhook_events_id_seq OWNED BY public.webhook_events.id;

--
-- Name: activities id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activities ALTER COLUMN id SET DEFAULT nextval('public.activities_id_seq'::regclass);

--
-- Name: activity_attachment_types id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_attachment_types ALTER COLUMN id SET DEFAULT nextval('public.activity_attachment_types_id_seq'::regclass);

--
-- Name: activity_consents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_consents ALTER COLUMN id SET DEFAULT nextval('public.activity_consents_id_seq'::regclass);

--
-- Name: activity_modalities id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_modalities ALTER COLUMN id SET DEFAULT nextval('public.activity_modalities_id_seq'::regclass);

--
-- Name: activity_prices id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_prices ALTER COLUMN id SET DEFAULT nextval('public.activity_prices_id_seq'::regclass);

--
-- Name: addresses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.addresses ALTER COLUMN id SET DEFAULT nextval('public.addresses_id_seq'::regclass);

--
-- Name: announcement_recipients id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.announcement_recipients ALTER COLUMN id SET DEFAULT nextval('public.announcement_recipients_id_seq'::regclass);

--
-- Name: announcements id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.announcements ALTER COLUMN id SET DEFAULT nextval('public.announcements_id_seq'::regclass);

--
-- Name: audit_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs ALTER COLUMN id SET DEFAULT nextval('public.audit_logs_id_seq'::regclass);

--
-- Name: billing_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_runs ALTER COLUMN id SET DEFAULT nextval('public.billing_runs_id_seq'::regclass);

--
-- Name: bookings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings ALTER COLUMN id SET DEFAULT nextval('public.bookings_id_seq'::regclass);

--
-- Name: concepts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.concepts ALTER COLUMN id SET DEFAULT nextval('public.concepts_id_seq'::regclass);

--
-- Name: contact_types id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_types ALTER COLUMN id SET DEFAULT nextval('public.contact_types_id_seq'::regclass);

--
-- Name: contacts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contacts ALTER COLUMN id SET DEFAULT nextval('public.contacts_id_seq'::regclass);

--
-- Name: custom_field_definitions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_field_definitions ALTER COLUMN id SET DEFAULT nextval('public.custom_field_definitions_id_seq'::regclass);

--
-- Name: custom_field_values id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_field_values ALTER COLUMN id SET DEFAULT nextval('public.custom_field_values_id_seq'::regclass);

--
-- Name: discount_codes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.discount_codes ALTER COLUMN id SET DEFAULT nextval('public.discount_codes_id_seq'::regclass);

--
-- Name: groups id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.groups ALTER COLUMN id SET DEFAULT nextval('public.groups_id_seq'::regclass);

--
-- Name: members id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.members ALTER COLUMN id SET DEFAULT nextval('public.members_id_seq'::regclass);

--
-- Name: membership_types id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.membership_types ALTER COLUMN id SET DEFAULT nextval('public.membership_types_id_seq'::regclass);

--
-- Name: notifications id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications ALTER COLUMN id SET DEFAULT nextval('public.notifications_id_seq'::regclass);

--
-- Name: organization_settings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_settings ALTER COLUMN id SET DEFAULT nextval('public.organization_settings_id_seq'::regclass);

--
-- Name: party id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.party ALTER COLUMN id SET DEFAULT nextval('public.party_id_seq'::regclass);

--
-- Name: payment_providers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_providers ALTER COLUMN id SET DEFAULT nextval('public.payment_providers_id_seq'::regclass);

--
-- Name: receipt_reminders id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_reminders ALTER COLUMN id SET DEFAULT nextval('public.receipt_reminders_id_seq'::regclass);

--
-- Name: receipts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts ALTER COLUMN id SET DEFAULT nextval('public.receipts_id_seq'::regclass);

--
-- Name: registration_attachments id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registration_attachments ALTER COLUMN id SET DEFAULT nextval('public.registration_attachments_id_seq'::regclass);

--
-- Name: registration_consents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registration_consents ALTER COLUMN id SET DEFAULT nextval('public.registration_consents_id_seq'::regclass);

--
-- Name: registrations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registrations ALTER COLUMN id SET DEFAULT nextval('public.registrations_id_seq'::regclass);

--
-- Name: reminders id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reminders ALTER COLUMN id SET DEFAULT nextval('public.reminders_id_seq'::regclass);

--
-- Name: remittance_receipts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.remittance_receipts ALTER COLUMN id SET DEFAULT nextval('public.remittance_receipts_id_seq'::regclass);

--
-- Name: remittances id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.remittances ALTER COLUMN id SET DEFAULT nextval('public.remittances_id_seq'::regclass);

--
-- Name: roles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles ALTER COLUMN id SET DEFAULT nextval('public.roles_id_seq'::regclass);

--
-- Name: sepa_mandates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sepa_mandates ALTER COLUMN id SET DEFAULT nextval('public.sepa_mandates_id_seq'::regclass);

--
-- Name: space_slots id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.space_slots ALTER COLUMN id SET DEFAULT nextval('public.space_slots_id_seq'::regclass);

--
-- Name: spaces id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.spaces ALTER COLUMN id SET DEFAULT nextval('public.spaces_id_seq'::regclass);

--
-- Name: user_identities id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_identities ALTER COLUMN id SET DEFAULT nextval('public.user_identities_id_seq'::regclass);

--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);

--
-- Name: webhook_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_events ALTER COLUMN id SET DEFAULT nextval('public.webhook_events_id_seq'::regclass);

--
-- Name: activities activities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activities
    ADD CONSTRAINT activities_pkey PRIMARY KEY (id);

--
-- Name: activities activities_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activities
    ADD CONSTRAINT activities_slug_key UNIQUE (slug);

--
-- Name: activity_attachment_types activity_attachment_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_attachment_types
    ADD CONSTRAINT activity_attachment_types_pkey PRIMARY KEY (id);

--
-- Name: activity_consents activity_consents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_consents
    ADD CONSTRAINT activity_consents_pkey PRIMARY KEY (id);

--
-- Name: activity_modalities activity_modalities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_modalities
    ADD CONSTRAINT activity_modalities_pkey PRIMARY KEY (id);

--
-- Name: activity_prices activity_prices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_prices
    ADD CONSTRAINT activity_prices_pkey PRIMARY KEY (id);

--
-- Name: addresses addresses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.addresses
    ADD CONSTRAINT addresses_pkey PRIMARY KEY (id);

--
-- Name: announcement_recipients announcement_recipients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.announcement_recipients
    ADD CONSTRAINT announcement_recipients_pkey PRIMARY KEY (id);

--
-- Name: announcements announcements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.announcements
    ADD CONSTRAINT announcements_pkey PRIMARY KEY (id);

--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);

--
-- Name: billing_runs billing_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_runs
    ADD CONSTRAINT billing_runs_pkey PRIMARY KEY (id);

--
-- Name: bookings bookings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings
    ADD CONSTRAINT bookings_pkey PRIMARY KEY (id);

--
-- Name: concepts concepts_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.concepts
    ADD CONSTRAINT concepts_code_key UNIQUE (code);

--
-- Name: concepts concepts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.concepts
    ADD CONSTRAINT concepts_pkey PRIMARY KEY (id);

--
-- Name: contact_channels contact_channels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_channels
    ADD CONSTRAINT contact_channels_pkey PRIMARY KEY (code);

--
-- Name: contact_types contact_types_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_types
    ADD CONSTRAINT contact_types_code_key UNIQUE (code);

--
-- Name: contact_types contact_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_types
    ADD CONSTRAINT contact_types_pkey PRIMARY KEY (id);

--
-- Name: contacts contacts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contacts
    ADD CONSTRAINT contacts_pkey PRIMARY KEY (id);

--
-- Name: custom_field_definitions custom_field_definitions_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_field_definitions
    ADD CONSTRAINT custom_field_definitions_key_key UNIQUE (key);

--
-- Name: custom_field_definitions custom_field_definitions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_field_definitions
    ADD CONSTRAINT custom_field_definitions_pkey PRIMARY KEY (id);

--
-- Name: custom_field_values custom_field_values_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_field_values
    ADD CONSTRAINT custom_field_values_pkey PRIMARY KEY (id);

--
-- Name: discount_codes discount_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.discount_codes
    ADD CONSTRAINT discount_codes_pkey PRIMARY KEY (id);

--
-- Name: groups groups_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.groups
    ADD CONSTRAINT groups_name_key UNIQUE (name);

--
-- Name: groups groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.groups
    ADD CONSTRAINT groups_pkey PRIMARY KEY (id);

--
-- Name: groups groups_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.groups
    ADD CONSTRAINT groups_slug_key UNIQUE (slug);

--
-- Name: invoice_sequences invoice_sequences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoice_sequences
    ADD CONSTRAINT invoice_sequences_pkey PRIMARY KEY (year);

--
-- Name: mail_transport_health mail_transport_health_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mail_transport_health
    ADD CONSTRAINT mail_transport_health_pkey PRIMARY KEY (provider);

--
-- Name: members members_member_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.members
    ADD CONSTRAINT members_member_number_key UNIQUE (member_number);

--
-- Name: members members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.members
    ADD CONSTRAINT members_pkey PRIMARY KEY (id);

--
-- Name: membership_types membership_types_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.membership_types
    ADD CONSTRAINT membership_types_name_key UNIQUE (name);

--
-- Name: membership_types membership_types_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.membership_types
    ADD CONSTRAINT membership_types_pkey PRIMARY KEY (id);

--
-- Name: membership_types membership_types_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.membership_types
    ADD CONSTRAINT membership_types_slug_key UNIQUE (slug);

--
-- Name: notifications notifications_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_pkey PRIMARY KEY (id);

--
-- Name: organization_settings organization_settings_party_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_settings
    ADD CONSTRAINT organization_settings_party_id_key UNIQUE (party_id);

--
-- Name: organization_settings organization_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_settings
    ADD CONSTRAINT organization_settings_pkey PRIMARY KEY (id);

--
-- Name: party party_id_kind_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.party
    ADD CONSTRAINT party_id_kind_key UNIQUE (id, kind);

--
-- Name: party_kinds party_kinds_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.party_kinds
    ADD CONSTRAINT party_kinds_pkey PRIMARY KEY (code);

--
-- Name: party party_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.party
    ADD CONSTRAINT party_pkey PRIMARY KEY (id);

--
-- Name: payment_providers payment_providers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payment_providers
    ADD CONSTRAINT payment_providers_pkey PRIMARY KEY (id);

--
-- Name: persons persons_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.persons
    ADD CONSTRAINT persons_pkey PRIMARY KEY (party_id);

--
-- Name: receipt_reminders receipt_reminders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_reminders
    ADD CONSTRAINT receipt_reminders_pkey PRIMARY KEY (id);

--
-- Name: receipts receipts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT receipts_pkey PRIMARY KEY (id);

--
-- Name: receipts receipts_receipt_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT receipts_receipt_number_key UNIQUE (receipt_number);

--
-- Name: registration_attachments registration_attachments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registration_attachments
    ADD CONSTRAINT registration_attachments_pkey PRIMARY KEY (id);

--
-- Name: registration_consents registration_consents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registration_consents
    ADD CONSTRAINT registration_consents_pkey PRIMARY KEY (id);

--
-- Name: registrations registrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registrations
    ADD CONSTRAINT registrations_pkey PRIMARY KEY (id);

--
-- Name: reminders reminders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reminders
    ADD CONSTRAINT reminders_pkey PRIMARY KEY (id);

--
-- Name: remittance_receipts remittance_receipts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.remittance_receipts
    ADD CONSTRAINT remittance_receipts_pkey PRIMARY KEY (id);

--
-- Name: remittance_sequences remittance_sequences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.remittance_sequences
    ADD CONSTRAINT remittance_sequences_pkey PRIMARY KEY (year);

--
-- Name: remittances remittances_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.remittances
    ADD CONSTRAINT remittances_pkey PRIMARY KEY (id);

--
-- Name: remittances remittances_remittance_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.remittances
    ADD CONSTRAINT remittances_remittance_number_key UNIQUE (remittance_number);

--
-- Name: role_permissions role_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_pkey PRIMARY KEY (role_id, permission_key);

--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (id);

--
-- Name: roles roles_slug_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_slug_key UNIQUE (slug);

--
-- Name: sepa_mandates sepa_mandates_mandate_reference_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sepa_mandates
    ADD CONSTRAINT sepa_mandates_mandate_reference_key UNIQUE (mandate_reference);

--
-- Name: sepa_mandates sepa_mandates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sepa_mandates
    ADD CONSTRAINT sepa_mandates_pkey PRIMARY KEY (id);

--
-- Name: space_slots space_slots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.space_slots
    ADD CONSTRAINT space_slots_pkey PRIMARY KEY (id);

--
-- Name: spaces spaces_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.spaces
    ADD CONSTRAINT spaces_pkey PRIMARY KEY (id);

--
-- Name: activity_modalities uq_activity_modality_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_modalities
    ADD CONSTRAINT uq_activity_modality_name UNIQUE (activity_id, name);

--
-- Name: billing_runs uq_billing_runs_frequency_period; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_runs
    ADD CONSTRAINT uq_billing_runs_frequency_period UNIQUE (frequency, period_start, period_end);

--
-- Name: contact_types uq_contact_types_id_channel; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_types
    ADD CONSTRAINT uq_contact_types_id_channel UNIQUE (id, channel);

--
-- Name: custom_field_values uq_custom_field_value_definition_party; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_field_values
    ADD CONSTRAINT uq_custom_field_value_definition_party UNIQUE (definition_id, party_id);

--
-- Name: discount_codes uq_discount_code_per_activity; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.discount_codes
    ADD CONSTRAINT uq_discount_code_per_activity UNIQUE (activity_id, code);

--
-- Name: user_identities uq_provider_subject; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_identities
    ADD CONSTRAINT uq_provider_subject UNIQUE (provider, provider_subject);

--
-- Name: receipts uq_receipts_redsys_ds_order; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT uq_receipts_redsys_ds_order UNIQUE (redsys_ds_order);

--
-- Name: registration_consents uq_registration_consent; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registration_consents
    ADD CONSTRAINT uq_registration_consent UNIQUE (registration_id, activity_consent_id);

--
-- Name: remittance_receipts uq_remittance_receipt; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.remittance_receipts
    ADD CONSTRAINT uq_remittance_receipt UNIQUE (remittance_id, receipt_id);

--
-- Name: user_identities user_identities_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_identities
    ADD CONSTRAINT user_identities_pkey PRIMARY KEY (id);

--
-- Name: user_roles user_roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_pkey PRIMARY KEY (user_id, role_id);

--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);

--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

--
-- Name: webhook_events webhook_events_external_event_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_events
    ADD CONSTRAINT webhook_events_external_event_id_key UNIQUE (external_event_id);

--
-- Name: webhook_events webhook_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_events
    ADD CONSTRAINT webhook_events_pkey PRIMARY KEY (id);

--
-- Name: idx_activities_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activities_is_active ON public.activities USING btree (is_active);

--
-- Name: idx_activities_is_featured; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activities_is_featured ON public.activities USING btree (is_featured);

--
-- Name: idx_activities_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activities_slug ON public.activities USING btree (slug);

--
-- Name: idx_activities_starts_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activities_starts_at ON public.activities USING btree (starts_at);

--
-- Name: idx_activities_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activities_status ON public.activities USING btree (status);

--
-- Name: idx_activity_attachment_types_activity_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_attachment_types_activity_id ON public.activity_attachment_types USING btree (activity_id);

--
-- Name: idx_activity_consents_activity_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_consents_activity_id ON public.activity_consents USING btree (activity_id);

--
-- Name: idx_activity_modalities_activity_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_modalities_activity_id ON public.activity_modalities USING btree (activity_id);

--
-- Name: idx_activity_prices_activity_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_prices_activity_id ON public.activity_prices USING btree (activity_id);

--
-- Name: idx_activity_prices_modality_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_activity_prices_modality_id ON public.activity_prices USING btree (modality_id);

--
-- Name: idx_audit_logs_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_logs_action ON public.audit_logs USING btree (action);

--
-- Name: idx_audit_logs_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_logs_created_at ON public.audit_logs USING btree (created_at);

--
-- Name: idx_audit_logs_table_record; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_logs_table_record ON public.audit_logs USING btree (table_name, record_id);

--
-- Name: idx_audit_logs_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_logs_user_id ON public.audit_logs USING btree (user_id);

--
-- Name: idx_contacts_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_contacts_type ON public.contacts USING btree (contact_type_id);

--
-- Name: idx_discount_codes_activity_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_discount_codes_activity_id ON public.discount_codes USING btree (activity_id);

--
-- Name: idx_discount_codes_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_discount_codes_code ON public.discount_codes USING btree (code);

--
-- Name: idx_groups_display_order; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_groups_display_order ON public.groups USING btree (display_order);

--
-- Name: idx_groups_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_groups_slug ON public.groups USING btree (slug);

--
-- Name: idx_members_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_members_is_active ON public.members USING btree (is_active);

--
-- Name: idx_members_joined_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_members_joined_at ON public.members USING btree (joined_at);

--
-- Name: idx_members_member_number; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_members_member_number ON public.members USING btree (member_number) WHERE (member_number IS NOT NULL);

--
-- Name: idx_members_membership_type_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_members_membership_type_id ON public.members USING btree (membership_type_id);

--
-- Name: idx_members_party_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_members_party_id ON public.members USING btree (party_id);

--
-- Name: idx_members_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_members_status ON public.members USING btree (status);

--
-- Name: idx_membership_types_display_order; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_membership_types_display_order ON public.membership_types USING btree (display_order);

--
-- Name: idx_membership_types_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_membership_types_is_active ON public.membership_types USING btree (is_active);

--
-- Name: idx_membership_types_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_membership_types_slug ON public.membership_types USING btree (slug);

--
-- Name: idx_persons_last_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_persons_last_name ON public.persons USING btree (last_name);

--
-- Name: idx_registration_attachments_registration_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_registration_attachments_registration_id ON public.registration_attachments USING btree (registration_id);

--
-- Name: idx_registration_consents_registration_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_registration_consents_registration_id ON public.registration_consents USING btree (registration_id);

--
-- Name: idx_registrations_activity_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_registrations_activity_id ON public.registrations USING btree (activity_id);

--
-- Name: idx_registrations_party_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_registrations_party_id ON public.registrations USING btree (party_id);

--
-- Name: idx_registrations_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_registrations_status ON public.registrations USING btree (status);

--
-- Name: idx_role_permissions_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_role_permissions_role ON public.role_permissions USING btree (role_id);

--
-- Name: idx_roles_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_roles_slug ON public.roles USING btree (slug);

--
-- Name: idx_user_identities_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_identities_user_id ON public.user_identities USING btree (user_id);

--
-- Name: idx_user_roles_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_roles_user ON public.user_roles USING btree (user_id);

--
-- Name: idx_users_is_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_is_active ON public.users USING btree (is_active);

--
-- Name: idx_users_party_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_party_id ON public.users USING btree (party_id);

--
-- Name: idx_users_reset_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_reset_token ON public.users USING btree (reset_token) WHERE (reset_token IS NOT NULL);

--
-- Name: idx_users_verification_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_users_verification_token ON public.users USING btree (verification_token) WHERE (verification_token IS NOT NULL);

--
-- Name: ix_addresses_party; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_addresses_party ON public.addresses USING btree (party_id) WHERE (party_id IS NOT NULL);

--
-- Name: ix_addresses_space; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_addresses_space ON public.addresses USING btree (space_id) WHERE (space_id IS NOT NULL);

--
-- Name: ix_announcement_recipients_announcement; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_announcement_recipients_announcement ON public.announcement_recipients USING btree (announcement_id);

--
-- Name: ix_announcements_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_announcements_created ON public.announcements USING btree (created_at);

--
-- Name: ix_announcements_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_announcements_status ON public.announcements USING btree (status);

--
-- Name: ix_billing_runs_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_billing_runs_id ON public.billing_runs USING btree (id);

--
-- Name: ix_billing_runs_triggered_started; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_billing_runs_triggered_started ON public.billing_runs USING btree (triggered_by, started_at);

--
-- Name: ix_bookings_party; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bookings_party ON public.bookings USING btree (party_id);

--
-- Name: ix_bookings_slot; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bookings_slot ON public.bookings USING btree (space_slot_id);

--
-- Name: ix_concepts_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_concepts_id ON public.concepts USING btree (id);

--
-- Name: ix_contacts_party; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_contacts_party ON public.contacts USING btree (party_id);

--
-- Name: ix_custom_field_definitions_active_order; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_custom_field_definitions_active_order ON public.custom_field_definitions USING btree (active, sort_order);

--
-- Name: ix_custom_field_values_party; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_custom_field_values_party ON public.custom_field_values USING btree (party_id);

--
-- Name: ix_notifications_user_unread; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notifications_user_unread ON public.notifications USING btree (user_id, read_at);

--
-- Name: ix_party_display_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_party_display_name ON public.party USING btree (display_name);

--
-- Name: ix_party_email; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_party_email ON public.party USING btree (email) WHERE (email IS NOT NULL);

--
-- Name: ix_party_kind; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_party_kind ON public.party USING btree (kind);

--
-- Name: ix_party_national_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_party_national_id ON public.party USING btree (national_id) WHERE (national_id IS NOT NULL);

--
-- Name: ix_payment_providers_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payment_providers_id ON public.payment_providers USING btree (id);

--
-- Name: ix_persons_stripe_customer_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_persons_stripe_customer_id ON public.persons USING btree (stripe_customer_id);

--
-- Name: ix_receipt_reminders_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_receipt_reminders_id ON public.receipt_reminders USING btree (id);

--
-- Name: ix_receipt_reminders_receipt; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_receipt_reminders_receipt ON public.receipt_reminders USING btree (receipt_id, sent_at);

--
-- Name: ix_receipts_booking_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_receipts_booking_id ON public.receipts USING btree (booking_id);

--
-- Name: ix_receipts_emission_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_receipts_emission_date ON public.receipts USING btree (emission_date);

--
-- Name: ix_receipts_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_receipts_id ON public.receipts USING btree (id);

--
-- Name: ix_receipts_origin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_receipts_origin ON public.receipts USING btree (origin);

--
-- Name: ix_receipts_party_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_receipts_party_id ON public.receipts USING btree (party_id);

--
-- Name: ix_receipts_rectifies_receipt_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_receipts_rectifies_receipt_id ON public.receipts USING btree (rectifies_receipt_id);

--
-- Name: ix_receipts_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_receipts_status ON public.receipts USING btree (status);

--
-- Name: ix_reminders_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reminders_id ON public.reminders USING btree (id);

--
-- Name: ix_reminders_open_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_reminders_open_due ON public.reminders USING btree (is_done, due_date);

--
-- Name: ix_remittance_receipts_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_remittance_receipts_id ON public.remittance_receipts USING btree (id);

--
-- Name: ix_remittance_receipts_receipt_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_remittance_receipts_receipt_id ON public.remittance_receipts USING btree (receipt_id);

--
-- Name: ix_remittance_receipts_remittance_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_remittance_receipts_remittance_id ON public.remittance_receipts USING btree (remittance_id);

--
-- Name: ix_remittances_emission_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_remittances_emission_date ON public.remittances USING btree (emission_date);

--
-- Name: ix_remittances_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_remittances_id ON public.remittances USING btree (id);

--
-- Name: ix_remittances_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_remittances_status ON public.remittances USING btree (status);

--
-- Name: ix_sepa_mandates_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sepa_mandates_id ON public.sepa_mandates USING btree (id);

--
-- Name: ix_sepa_mandates_party_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sepa_mandates_party_id ON public.sepa_mandates USING btree (party_id);

--
-- Name: ix_sepa_mandates_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_sepa_mandates_status ON public.sepa_mandates USING btree (status);

--
-- Name: ix_space_slots_series; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_space_slots_series ON public.space_slots USING btree (series_id);

--
-- Name: ix_space_slots_space_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_space_slots_space_date ON public.space_slots USING btree (space_id, slot_date);

--
-- Name: ix_spaces_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_spaces_active ON public.spaces USING btree (is_active);

--
-- Name: ix_webhook_events_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_webhook_events_id ON public.webhook_events USING btree (id);

--
-- Name: ix_webhook_events_provider_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_webhook_events_provider_status ON public.webhook_events USING btree (provider_type, status);

--
-- Name: uq_addresses_primary_per_party; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_addresses_primary_per_party ON public.addresses USING btree (party_id) WHERE ((party_id IS NOT NULL) AND is_primary);

--
-- Name: uq_bookings_party_slot_active; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_bookings_party_slot_active ON public.bookings USING btree (space_slot_id, party_id) WHERE ((status)::text = ANY ((ARRAY['booked'::character varying, 'waitlisted'::character varying])::text[]));

--
-- Name: uq_contacts_one_primary_per_channel; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_contacts_one_primary_per_channel ON public.contacts USING btree (party_id, channel) WHERE is_primary;

--
-- Name: uq_members_one_active_per_party; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_members_one_active_per_party ON public.members USING btree (party_id) WHERE is_active;

--
-- Name: uq_membership_types_is_default; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_membership_types_is_default ON public.membership_types USING btree (is_default) WHERE is_default;

--
-- Name: uq_registration_active_party; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_registration_active_party ON public.registrations USING btree (activity_id, party_id) WHERE ((status)::text <> 'cancelled'::text);

--
-- Name: uq_sepa_mandates_one_active_per_party; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_sepa_mandates_one_active_per_party ON public.sepa_mandates USING btree (party_id) WHERE (((status)::text = 'active'::text) AND (is_active = true));

--
-- Name: uq_users_email_lower; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_users_email_lower ON public.users USING btree (lower(btrim((email)::text)));

--
-- Name: uq_users_one_active_per_party; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_users_one_active_per_party ON public.users USING btree (party_id) WHERE is_active;

--
-- Name: persons trg_party_display_name; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_party_display_name AFTER INSERT OR UPDATE OF first_name, last_name ON public.persons FOR EACH ROW EXECUTE FUNCTION public.party_sync_display_name_from_person();

--
-- Name: activities activities_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activities
    ADD CONSTRAINT activities_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;

--
-- Name: activity_attachment_types activity_attachment_types_activity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_attachment_types
    ADD CONSTRAINT activity_attachment_types_activity_id_fkey FOREIGN KEY (activity_id) REFERENCES public.activities(id) ON DELETE CASCADE;

--
-- Name: activity_consents activity_consents_activity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_consents
    ADD CONSTRAINT activity_consents_activity_id_fkey FOREIGN KEY (activity_id) REFERENCES public.activities(id) ON DELETE CASCADE;

--
-- Name: activity_modalities activity_modalities_activity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_modalities
    ADD CONSTRAINT activity_modalities_activity_id_fkey FOREIGN KEY (activity_id) REFERENCES public.activities(id) ON DELETE CASCADE;

--
-- Name: activity_prices activity_prices_activity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_prices
    ADD CONSTRAINT activity_prices_activity_id_fkey FOREIGN KEY (activity_id) REFERENCES public.activities(id) ON DELETE CASCADE;

--
-- Name: activity_prices activity_prices_modality_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.activity_prices
    ADD CONSTRAINT activity_prices_modality_id_fkey FOREIGN KEY (modality_id) REFERENCES public.activity_modalities(id) ON DELETE SET NULL;

--
-- Name: addresses addresses_party_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.addresses
    ADD CONSTRAINT addresses_party_id_fkey FOREIGN KEY (party_id) REFERENCES public.party(id) ON DELETE CASCADE;

--
-- Name: addresses addresses_space_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.addresses
    ADD CONSTRAINT addresses_space_id_fkey FOREIGN KEY (space_id) REFERENCES public.spaces(id) ON DELETE CASCADE;

--
-- Name: announcement_recipients announcement_recipients_announcement_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.announcement_recipients
    ADD CONSTRAINT announcement_recipients_announcement_id_fkey FOREIGN KEY (announcement_id) REFERENCES public.announcements(id) ON DELETE CASCADE;

--
-- Name: announcement_recipients announcement_recipients_member_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.announcement_recipients
    ADD CONSTRAINT announcement_recipients_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.members(id) ON DELETE CASCADE;

--
-- Name: announcement_recipients announcement_recipients_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.announcement_recipients
    ADD CONSTRAINT announcement_recipients_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;

--
-- Name: announcements announcements_created_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.announcements
    ADD CONSTRAINT announcements_created_by_user_id_fkey FOREIGN KEY (created_by_user_id) REFERENCES public.users(id);

--
-- Name: audit_logs audit_logs_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;

--
-- Name: billing_runs billing_runs_triggered_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.billing_runs
    ADD CONSTRAINT billing_runs_triggered_by_user_id_fkey FOREIGN KEY (triggered_by_user_id) REFERENCES public.users(id);

--
-- Name: bookings bookings_cancelled_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings
    ADD CONSTRAINT bookings_cancelled_by_user_id_fkey FOREIGN KEY (cancelled_by_user_id) REFERENCES public.users(id) ON DELETE SET NULL;

--
-- Name: bookings bookings_party_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings
    ADD CONSTRAINT bookings_party_id_fkey FOREIGN KEY (party_id) REFERENCES public.party(id) ON DELETE CASCADE;

--
-- Name: bookings bookings_space_slot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bookings
    ADD CONSTRAINT bookings_space_slot_id_fkey FOREIGN KEY (space_slot_id) REFERENCES public.space_slots(id) ON DELETE CASCADE;

--
-- Name: contact_types contact_types_channel_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contact_types
    ADD CONSTRAINT contact_types_channel_fkey FOREIGN KEY (channel) REFERENCES public.contact_channels(code);

--
-- Name: contacts contacts_channel_matches_type; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contacts
    ADD CONSTRAINT contacts_channel_matches_type FOREIGN KEY (contact_type_id, channel) REFERENCES public.contact_types(id, channel) ON DELETE SET NULL;

--
-- Name: contacts contacts_party_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.contacts
    ADD CONSTRAINT contacts_party_id_fkey FOREIGN KEY (party_id) REFERENCES public.party(id) ON DELETE CASCADE;

--
-- Name: custom_field_values custom_field_values_definition_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_field_values
    ADD CONSTRAINT custom_field_values_definition_id_fkey FOREIGN KEY (definition_id) REFERENCES public.custom_field_definitions(id) ON DELETE CASCADE;

--
-- Name: custom_field_values custom_field_values_party_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.custom_field_values
    ADD CONSTRAINT custom_field_values_party_id_fkey FOREIGN KEY (party_id) REFERENCES public.party(id) ON DELETE CASCADE;

--
-- Name: discount_codes discount_codes_activity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.discount_codes
    ADD CONSTRAINT discount_codes_activity_id_fkey FOREIGN KEY (activity_id) REFERENCES public.activities(id) ON DELETE CASCADE;

--
-- Name: members fk_members_membership_reverted_from_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.members
    ADD CONSTRAINT fk_members_membership_reverted_from_id FOREIGN KEY (membership_reverted_from_id) REFERENCES public.membership_types(id) ON DELETE SET NULL;

--
-- Name: receipts fk_receipts_booking_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT fk_receipts_booking_id FOREIGN KEY (booking_id) REFERENCES public.bookings(id) ON DELETE SET NULL;

--
-- Name: receipts fk_receipts_purchased_membership_type_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT fk_receipts_purchased_membership_type_id FOREIGN KEY (purchased_membership_type_id) REFERENCES public.membership_types(id) ON DELETE SET NULL;

--
-- Name: receipts fk_receipts_rectifies_receipt_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT fk_receipts_rectifies_receipt_id FOREIGN KEY (rectifies_receipt_id) REFERENCES public.receipts(id) ON DELETE RESTRICT;

--
-- Name: receipts fk_receipts_remittance_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT fk_receipts_remittance_id FOREIGN KEY (remittance_id) REFERENCES public.remittances(id);

--
-- Name: registrations fk_registrations_discount_code_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registrations
    ADD CONSTRAINT fk_registrations_discount_code_id FOREIGN KEY (discount_code_id) REFERENCES public.discount_codes(id) ON DELETE SET NULL;

--
-- Name: members members_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.members
    ADD CONSTRAINT members_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;

--
-- Name: members members_guardian_party_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.members
    ADD CONSTRAINT members_guardian_party_id_fkey FOREIGN KEY (guardian_party_id) REFERENCES public.persons(party_id) ON DELETE SET NULL;

--
-- Name: members members_membership_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.members
    ADD CONSTRAINT members_membership_type_id_fkey FOREIGN KEY (membership_type_id) REFERENCES public.membership_types(id) ON DELETE SET NULL;

--
-- Name: members members_party_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.members
    ADD CONSTRAINT members_party_id_fkey FOREIGN KEY (party_id) REFERENCES public.party(id) ON DELETE CASCADE;

--
-- Name: membership_types membership_types_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.membership_types
    ADD CONSTRAINT membership_types_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id) ON DELETE SET NULL;

--
-- Name: notifications notifications_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications
    ADD CONSTRAINT notifications_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

--
-- Name: organization_settings organization_settings_party_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.organization_settings
    ADD CONSTRAINT organization_settings_party_id_fkey FOREIGN KEY (party_id) REFERENCES public.party(id);

--
-- Name: party party_kind_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.party
    ADD CONSTRAINT party_kind_fkey FOREIGN KEY (kind) REFERENCES public.party_kinds(code);

--
-- Name: persons persons_party_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.persons
    ADD CONSTRAINT persons_party_fk FOREIGN KEY (party_id, kind) REFERENCES public.party(id, kind) ON DELETE CASCADE;

--
-- Name: receipt_reminders receipt_reminders_receipt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_reminders
    ADD CONSTRAINT receipt_reminders_receipt_id_fkey FOREIGN KEY (receipt_id) REFERENCES public.receipts(id);

--
-- Name: receipt_reminders receipt_reminders_triggered_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipt_reminders
    ADD CONSTRAINT receipt_reminders_triggered_by_user_id_fkey FOREIGN KEY (triggered_by_user_id) REFERENCES public.users(id);

--
-- Name: receipts receipts_concept_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT receipts_concept_id_fkey FOREIGN KEY (concept_id) REFERENCES public.concepts(id);

--
-- Name: receipts receipts_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT receipts_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);

--
-- Name: receipts receipts_party_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT receipts_party_id_fkey FOREIGN KEY (party_id) REFERENCES public.party(id);

--
-- Name: receipts receipts_registration_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT receipts_registration_id_fkey FOREIGN KEY (registration_id) REFERENCES public.registrations(id);

--
-- Name: registration_attachments registration_attachments_attachment_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registration_attachments
    ADD CONSTRAINT registration_attachments_attachment_type_id_fkey FOREIGN KEY (attachment_type_id) REFERENCES public.activity_attachment_types(id) ON DELETE SET NULL;

--
-- Name: registration_attachments registration_attachments_registration_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registration_attachments
    ADD CONSTRAINT registration_attachments_registration_id_fkey FOREIGN KEY (registration_id) REFERENCES public.registrations(id) ON DELETE CASCADE;

--
-- Name: registration_consents registration_consents_activity_consent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registration_consents
    ADD CONSTRAINT registration_consents_activity_consent_id_fkey FOREIGN KEY (activity_consent_id) REFERENCES public.activity_consents(id) ON DELETE CASCADE;

--
-- Name: registration_consents registration_consents_registration_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registration_consents
    ADD CONSTRAINT registration_consents_registration_id_fkey FOREIGN KEY (registration_id) REFERENCES public.registrations(id) ON DELETE CASCADE;

--
-- Name: registrations registrations_activity_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registrations
    ADD CONSTRAINT registrations_activity_id_fkey FOREIGN KEY (activity_id) REFERENCES public.activities(id) ON DELETE CASCADE;

--
-- Name: registrations registrations_cancelled_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registrations
    ADD CONSTRAINT registrations_cancelled_by_fkey FOREIGN KEY (cancelled_by) REFERENCES public.users(id) ON DELETE SET NULL;

--
-- Name: registrations registrations_modality_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registrations
    ADD CONSTRAINT registrations_modality_id_fkey FOREIGN KEY (modality_id) REFERENCES public.activity_modalities(id) ON DELETE SET NULL;

--
-- Name: registrations registrations_party_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registrations
    ADD CONSTRAINT registrations_party_id_fkey FOREIGN KEY (party_id) REFERENCES public.party(id) ON DELETE CASCADE;

--
-- Name: registrations registrations_price_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.registrations
    ADD CONSTRAINT registrations_price_id_fkey FOREIGN KEY (price_id) REFERENCES public.activity_prices(id) ON DELETE SET NULL;

--
-- Name: reminders reminders_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reminders
    ADD CONSTRAINT reminders_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id) ON DELETE SET NULL;

--
-- Name: remittance_receipts remittance_receipts_receipt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.remittance_receipts
    ADD CONSTRAINT remittance_receipts_receipt_id_fkey FOREIGN KEY (receipt_id) REFERENCES public.receipts(id) ON DELETE CASCADE;

--
-- Name: remittance_receipts remittance_receipts_remittance_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.remittance_receipts
    ADD CONSTRAINT remittance_receipts_remittance_id_fkey FOREIGN KEY (remittance_id) REFERENCES public.remittances(id) ON DELETE CASCADE;

--
-- Name: remittances remittances_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.remittances
    ADD CONSTRAINT remittances_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.users(id);

--
-- Name: role_permissions role_permissions_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.role_permissions
    ADD CONSTRAINT role_permissions_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE CASCADE;

--
-- Name: sepa_mandates sepa_mandates_party_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sepa_mandates
    ADD CONSTRAINT sepa_mandates_party_id_fkey FOREIGN KEY (party_id) REFERENCES public.party(id);

--
-- Name: space_slots space_slots_space_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.space_slots
    ADD CONSTRAINT space_slots_space_id_fkey FOREIGN KEY (space_id) REFERENCES public.spaces(id) ON DELETE CASCADE;

--
-- Name: user_identities user_identities_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_identities
    ADD CONSTRAINT user_identities_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

--
-- Name: user_roles user_roles_assigned_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_assigned_by_fkey FOREIGN KEY (assigned_by) REFERENCES public.users(id) ON DELETE SET NULL;

--
-- Name: user_roles user_roles_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(id) ON DELETE RESTRICT;

--
-- Name: user_roles user_roles_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

--
-- Name: users users_party_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_party_id_fkey FOREIGN KEY (party_id) REFERENCES public.party(id) ON DELETE CASCADE;

--
-- Name: webhook_events webhook_events_receipt_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_events
    ADD CONSTRAINT webhook_events_receipt_id_fkey FOREIGN KEY (receipt_id) REFERENCES public.receipts(id);

--
-- PostgreSQL database dump complete
--

