import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { TextInput, PasswordInput, Button, Paper, Title, Stack, Alert } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useAuth } from './AuthContext';
import { ApiError } from '../api/client';

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const form = useForm({ initialValues: { usuario: '', clave: '' } });

  async function onSubmit(values: { usuario: string; clave: string }) {
    setError(null);
    try {
      await login(values.usuario, values.clave);
      navigate('/clientes');
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Error de conexión');
    }
  }

  return (
    <Paper maw={360} mx="auto" mt={120} p="xl" withBorder>
      <Title order={2} mb="md">Sistema XML</Title>
      <form onSubmit={form.onSubmit(onSubmit)}>
        <Stack>
          {error && <Alert color="red">{error}</Alert>}
          <TextInput label="Usuario" {...form.getInputProps('usuario')} />
          <PasswordInput label="Contraseña" {...form.getInputProps('clave')} />
          <Button type="submit">Ingresar</Button>
        </Stack>
      </form>
    </Paper>
  );
}
