import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { projectsApi, ProjectCreateInput } from '../../api/projects';
import { useToast } from '../../components/feedback/Toast';
import { Card } from '../../components/ui/Card';
import { ProjectForm } from '../../components/forms/ProjectForm';
import { parseApiError } from '../../api/errorHandler';

export const ProjectCreatePage: React.FC = () => {
  const navigate = useNavigate();
  const { success, error } = useToast();
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (data: ProjectCreateInput) => {
    setIsLoading(true);
    try {
      const project = await projectsApi.create(data);
      success(`Proyek ${project.project_name} (${project.project_code}) berhasil dibuat.`);
      navigate(`/projects/${project.id}`);
    } catch (err: unknown) {
      error(`Gagal menyimpan proyek: ${parseApiError(err).message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate('/projects')}
          className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-200/60 hover:text-slate-900 transition-colors cursor-pointer"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            Tambah Proyek Baru
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Daftarkan kontrak kerja atau proyek baru untuk pengelompokan biaya dan piutang.
          </p>
        </div>
      </div>

      <Card>
        <ProjectForm
          onSubmit={handleSubmit}
          isLoading={isLoading}
          onCancel={() => navigate('/projects')}
        />
      </Card>
    </div>
  );
};
