# Introducción a la guía del administrador

Esta guía está dirigida al **personal que gestiona la organización** desde el panel de
administración de Memship: altas de socios, actividades, cobros, comunicaciones y
configuración.

> **In English:** [Introduction to the administrator guide](../../en/admin-guide/overview.md).

> **Idioma.** Las guías del administrador y del socio se escriben primero en español
> (`docs/es/`), porque quienes gestionan un club y sus socios son mayoritariamente
> hispanohablantes. Todas tienen versión en inglés (`docs/en/`); la traducción al catalán
> (`docs/ca/`) está en curso, y hasta que exista se sirve la página en español.

## Roles

Memship trae tres roles del sistema:

| Rol                    | Qué puede hacer                                                              |
|------------------------|------------------------------------------------------------------------------|
| **Superadministrador** | Administración a nivel de plataforma, incluida la configuración de las pasarelas de pago. |
| **Administrador de la organización** | Gestión diaria: socios, actividades, facturación y comunicaciones. |
| **Socio**              | Uso del portal del socio: perfil, actividades, pagos, carné y reservas.       |

La mayor parte de esta guía se refiere al **administrador de la organización**. El
superadministrador puede además crear **roles personalizados** con los permisos que elija; ver
[Roles y permisos](../reference/roles-and-permissions.md).

## Iniciar sesión

El acceso se realiza con **correo electrónico y contraseña**. Si has olvidado la contraseña,
usa el enlace de recuperación de la pantalla de inicio de sesión (requiere que el
[envío de correo](../self-hosting/email.md) esté configurado).

## Áreas del panel

El panel de administración se organiza en torno a estas áreas:

- **Panel (Dashboard)**, resumen con gráficos de estado de socios y de recibos, e importes
  pendientes, pagados y vencidos.
- **[Socios](members.md)**, ciclo de vida completo (alta, cambios de estado, baja), tipos de
  cuota, grupos y soporte para menores con tutor.
- **[Entidades](entities.md)**, empresas, fundaciones y organismos con los que trata el club,
  con recibos a su nombre (donaciones) sin necesidad de hacerlos socios.
- **[Actividades](activities.md)**, creación y publicación, inscripciones con control de
  elegibilidad, lista de espera, códigos de descuento, consentimientos y adjuntos.
- **[Pagos](payments.md)**, recibos, generación de cuotas, IVA, facturación, generación de
  PDF y cobro en línea (Stripe, Redsys/Bizum).
- **[Donaciones](donations.md)**: los tres caminos para recibir una donación, y qué registro
  deja cada uno.
- **[SEPA](sepa.md)**, mandatos de domiciliación, remesas (XML pain.008) e importación de
  devoluciones.
- **[Comunicaciones](communications.md)**, anuncios a todos los socios, a un grupo o a un
  tipo de cuota.
- **[Carné digital](member-cards.md)**, carné en PDF con número de socio y check-in por QR.
- **[Campos personalizados](custom-fields.md)**, campos de perfil configurables por la
  organización.
- **[Informes](reports.md)**, exportaciones CSV, panel financiero y resumen anual.
- **[Configuración](settings.md)**, marca (nombre, color, logotipo), dirección, datos
  bancarios, facturación y automatizaciones.

> La reserva de espacios (**Simple Bookings**) aún no forma parte de una versión publicada y se
> documentará cuando se libere.

## Configuración inicial

Antes de dar de alta a socios reales, completa la [configuración inicial](../getting-started/first-setup.md):
datos de la organización, marca, datos bancarios y facturación, y verifica el envío de correo.

## Páginas de la guía

Cada área (Socios, Actividades, Pagos, etc.) tiene su propia página. El
[índice de la documentación](../README.md) las enumera todas.
