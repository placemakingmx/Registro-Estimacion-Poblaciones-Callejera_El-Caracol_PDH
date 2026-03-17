# privacy/consent section

# Add a privacy consent checkbox

consent_checkbox = st.checkbox("Confirmo que se explicó el aviso de privacidad y se obtuvo consentimiento")

if not consent_checkbox:
    st.error("You must confirm privacy consent to proceed.")
else:
    # Proceed with the rest of the submission process
    # Your code for handling the submission goes here

# Add link to terms and conditions
st.markdown("[Términos y Condiciones](app/pages/terminos_condiciones.py)"),

# Disable the 'Registrar Entrevista' button unless the checkbox is checked
if not consent_checkbox:
    disable_button = True
else:
    disable_button = False

st.button("Registrar Entrevista", disabled=disable_button)