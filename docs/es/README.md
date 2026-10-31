# Documentación de Memship (castellano)

Documentación para **quien aloja Memship**, **quien administra una entidad** y **las personas
socias**. Este es el árbol en castellano; el inglés está en [`../en/README.md`](../en/README.md).

## Qué versión describe esta documentación

Estas páginas describen memship 3.0.1 — la versión publicada actual — más lo que se haya
fusionado desde que se etiquetó. Se publican desde la rama principal, así que un cambio aparece
aquí cuando se fusiona y no cuando sale la versión siguiente.

**Para saber qué versión ejecuta tu instancia**, pregúntaselo:

```bash
curl -s http://localhost/api/v1/health   # {"status":"healthy","version":"2.19.0",...}
```

`version` es la etiqueta de imagen con la que se desplegó. Si dice `latest`, la instalación no
está fijada a una versión y desde aquí no se puede saber — mira
[Actualizar](../en/self-hosting/upgrading.md).

**Si tu instancia es más antigua**, lee la documentación tal como estaba para tu versión en vez de
esta. Cada etiqueta lleva su propia copia, así que pon tu versión en la ruta:

```
https://github.com/marcandreuf/memship/blob/v2.18.0/docs/README.md
```

Lo que cambió entre tu versión y esta está en la
[página de versiones](https://github.com/marcandreuf/memship/releases), donde las notas de cada
una recogen los cambios de comportamiento y las migraciones que no conviene saltarse.

## Primeros pasos

- [Qué necesitas para ejecutar Memship](getting-started/what-you-need.md) — el servidor, el
  dominio, el correo y lo que cuestan, medido en vez de estimado. Para decidir, antes de instalar

El resto de las páginas de instalación están por ahora solo en inglés:
[Quick start](../en/getting-started/quickstart.md),
[Installation](../en/getting-started/installation.md) y
[First-time setup](../en/getting-started/first-setup.md).

## Guía del administrador (admin guide)

Para el personal que gestiona la organización desde el panel de administración.

- [Introducción](admin-guide/overview.md) — roles, navegación y panel
- [Socios](admin-guide/members.md) — ciclo de vida, tipos de membresía, grupos
- [Actividades](admin-guide/activities.md) — inscripciones, modalidades, descuentos
- [Pagos y recibos](admin-guide/payments.md) — recibos, cuotas, IVA, pago en línea
- [Domiciliación SEPA](admin-guide/sepa.md) — mandatos y remesas
- [Comunicaciones](admin-guide/communications.md) — anuncios a los socios
- [Carné digital](admin-guide/member-cards.md) — carné QR y control de acceso
- [Campos de perfil](admin-guide/custom-fields.md) — campos personalizados
- [Informes y panel](admin-guide/reports.md) — panel, resumen anual, exportaciones
- [Configuración](admin-guide/settings.md) — organización, facturación, automatizaciones
- [Integrations](../en/admin-guide/integrations.md) — SSO (Google, Apple) y correo, paso a paso _(en inglés)_
- [Payment providers](../en/admin-guide/payment-providers.md) — conectar Stripe, Redsys y Bizum _(en inglés)_

## Guía del socio (member guide)

Para las personas socias que usan el portal.

- [Tu cuenta y tu perfil](member-guide/account.md) — acceso, perfil, idioma, foto
- [Actividades](member-guide/activities.md) — inscribirse, lista de espera
- [Pagos y recibos](member-guide/payments.md) — mis recibos, pagar online, forma de pago
- [Carné digital](member-guide/member-card.md) — carné QR

## Alojar Memship (operadores)

Estas páginas están por ahora solo en inglés, y su cobertura en castellano se sigue en
[#423](https://github.com/marcandreuf/memship/issues/423):

- [Your organisation's domain](../en/self-hosting/domain-and-dns.md) — el nombre de máquina y sus
  registros DNS, cuando el dominio es de la entidad y no tuyo
- [Configuration reference](../en/self-hosting/configuration.md) — todas las variables de entorno
- [Feature flags](../en/self-hosting/feature-flags.md) — los veintiún interruptores de módulo
- [Email delivery](../en/self-hosting/email.md) — Resend, Gmail o cualquier servidor SMTP
- [Backups & restore](../en/self-hosting/backups-and-restore.md) — copias de seguridad y restauración
- [Upgrading](../en/self-hosting/upgrading.md) — etiquetas de imagen y migraciones
- [Troubleshooting](../en/self-hosting/troubleshooting.md) — cuando algo no arranca

## Referencia

- [Roles y permisos](reference/roles-and-permissions.md)
- Preguntas frecuentes — _pendiente_
- Glosario — _pendiente_

> **Reserva de espacios** (Simple Bookings) va en las imágenes publicadas — `/api/v1/bookings`
> está en la API y el comando de puesta en marcha siembra espacios, franjas y lista de espera —
> pero **todavía no tiene página en la guía del administrador ni en la del socio**. Es un hueco de
> documentación, no una función que falte.
