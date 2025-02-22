import os
from copy import deepcopy

import pytest
import torch
from torch.optim import Adam

from pythae.customexception import BadInheritanceError
from pythae.models.base.base_utils import ModelOutput
from pythae.models import WAE_MMD, WAE_MMD_Config, AutoModel
from pythae.samplers import NormalSamplerConfig, GaussianMixtureSamplerConfig, MAFSamplerConfig, IAFSamplerConfig
from pythae.trainers import BaseTrainer, BaseTrainerConfig
from pythae.pipelines import TrainingPipeline, GenerationPipeline
from tests.data.custom_architectures import (
    Decoder_AE_Conv,
    Encoder_AE_Conv,
    NetBadInheritance,
)

PATH = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(params=[WAE_MMD_Config(), WAE_MMD_Config(latent_dim=5)])
def model_configs_no_input_dim(request):
    return request.param


@pytest.fixture(
    params=[
        WAE_MMD_Config(input_dim=(1, 28, 28), latent_dim=10, kernel_choice="rbf", scales=None),
        WAE_MMD_Config(
            input_dim=(1, 2, 18), latent_dim=5, reg_weight=1.0, kernel_bandwidth=0.2
        ),
    ]
)
def model_configs(request):
    return request.param


@pytest.fixture
def custom_encoder(model_configs):
    return Encoder_AE_Conv(model_configs)


@pytest.fixture
def custom_decoder(model_configs):
    return Decoder_AE_Conv(model_configs)


class Test_Model_Building:
    @pytest.fixture()
    def bad_net(self):
        return NetBadInheritance()

    def test_build_model(self, model_configs):
        model = WAE_MMD(model_configs)
        assert all(
            [
                model.input_dim == model_configs.input_dim,
                model.latent_dim == model_configs.latent_dim,
            ]
        )

    def test_raises_bad_inheritance(self, model_configs, bad_net):
        with pytest.raises(BadInheritanceError):
            model = WAE_MMD(model_configs, encoder=bad_net)

        with pytest.raises(BadInheritanceError):
            model = WAE_MMD(model_configs, decoder=bad_net)

    def test_raises_no_input_dim(
        self, model_configs_no_input_dim, custom_encoder, custom_decoder
    ):
        with pytest.raises(AttributeError):
            model = WAE_MMD(model_configs_no_input_dim)

        with pytest.raises(AttributeError):
            model = WAE_MMD(model_configs_no_input_dim, encoder=custom_encoder)

        with pytest.raises(AttributeError):
            model = WAE_MMD(model_configs_no_input_dim, decoder=custom_decoder)

        model = WAE_MMD(
            model_configs_no_input_dim, encoder=custom_encoder, decoder=custom_decoder
        )

    def test_build_custom_arch(self, model_configs, custom_encoder, custom_decoder):

        model = WAE_MMD(model_configs, encoder=custom_encoder, decoder=custom_decoder)

        assert model.encoder == custom_encoder
        assert not model.model_config.uses_default_encoder
        assert model.decoder == custom_decoder
        assert not model.model_config.uses_default_decoder

        model = WAE_MMD(model_configs, encoder=custom_encoder)

        assert model.encoder == custom_encoder
        assert not model.model_config.uses_default_encoder
        assert model.model_config.uses_default_decoder

        model = WAE_MMD(model_configs, decoder=custom_decoder)

        assert model.model_config.uses_default_encoder
        assert model.decoder == custom_decoder
        assert not model.model_config.uses_default_decoder


class Test_Model_Saving:
    def test_default_model_saving(self, tmpdir, model_configs):

        tmpdir.mkdir("dummy_folder")
        dir_path = dir_path = os.path.join(tmpdir, "dummy_folder")

        model = WAE_MMD(model_configs)

        model.state_dict()["encoder.layers.0.0.weight"][0] = 0

        model.save(dir_path=dir_path)

        assert set(os.listdir(dir_path)) == set(["model_config.json", "model.pt"])

        # reload model
        model_rec = AutoModel.load_from_folder(dir_path)

        # check configs are the same
        assert model_rec.model_config.__dict__ == model.model_config.__dict__

        assert all(
            [
                torch.equal(model_rec.state_dict()[key], model.state_dict()[key])
                for key in model.state_dict().keys()
            ]
        )

    def test_custom_encoder_model_saving(self, tmpdir, model_configs, custom_encoder):

        tmpdir.mkdir("dummy_folder")
        dir_path = dir_path = os.path.join(tmpdir, "dummy_folder")

        model = WAE_MMD(model_configs, encoder=custom_encoder)

        model.state_dict()["encoder.layers.0.0.weight"][0] = 0

        model.save(dir_path=dir_path)

        assert set(os.listdir(dir_path)) == set(
            ["model_config.json", "model.pt", "encoder.pkl"]
        )

        # reload model
        model_rec = AutoModel.load_from_folder(dir_path)

        # check configs are the same
        assert model_rec.model_config.__dict__ == model.model_config.__dict__

        assert all(
            [
                torch.equal(model_rec.state_dict()[key], model.state_dict()[key])
                for key in model.state_dict().keys()
            ]
        )

    def test_custom_decoder_model_saving(self, tmpdir, model_configs, custom_decoder):

        tmpdir.mkdir("dummy_folder")
        dir_path = dir_path = os.path.join(tmpdir, "dummy_folder")

        model = WAE_MMD(model_configs, decoder=custom_decoder)

        model.state_dict()["encoder.layers.0.0.weight"][0] = 0

        model.save(dir_path=dir_path)

        assert set(os.listdir(dir_path)) == set(
            ["model_config.json", "model.pt", "decoder.pkl"]
        )

        # reload model
        model_rec = AutoModel.load_from_folder(dir_path)

        # check configs are the same
        assert model_rec.model_config.__dict__ == model.model_config.__dict__

        assert all(
            [
                torch.equal(model_rec.state_dict()[key], model.state_dict()[key])
                for key in model.state_dict().keys()
            ]
        )

    def test_full_custom_model_saving(
        self, tmpdir, model_configs, custom_encoder, custom_decoder
    ):

        tmpdir.mkdir("dummy_folder")
        dir_path = dir_path = os.path.join(tmpdir, "dummy_folder")

        model = WAE_MMD(model_configs, encoder=custom_encoder, decoder=custom_decoder)

        model.state_dict()["encoder.layers.0.0.weight"][0] = 0

        model.save(dir_path=dir_path)

        assert set(os.listdir(dir_path)) == set(
            ["model_config.json", "model.pt", "encoder.pkl", "decoder.pkl"]
        )

        # reload model
        model_rec = AutoModel.load_from_folder(dir_path)

        # check configs are the same
        assert model_rec.model_config.__dict__ == model.model_config.__dict__

        assert all(
            [
                torch.equal(model_rec.state_dict()[key], model.state_dict()[key])
                for key in model.state_dict().keys()
            ]
        )

    def test_raises_missing_files(
        self, tmpdir, model_configs, custom_encoder, custom_decoder
    ):

        tmpdir.mkdir("dummy_folder")
        dir_path = dir_path = os.path.join(tmpdir, "dummy_folder")

        model = WAE_MMD(model_configs, encoder=custom_encoder, decoder=custom_decoder)

        model.state_dict()["encoder.layers.0.0.weight"][0] = 0

        model.save(dir_path=dir_path)

        os.remove(os.path.join(dir_path, "decoder.pkl"))

        # check raises decoder.pkl is missing
        with pytest.raises(FileNotFoundError):
            model_rec = AutoModel.load_from_folder(dir_path)

        os.remove(os.path.join(dir_path, "encoder.pkl"))

        # check raises encoder.pkl is missing
        with pytest.raises(FileNotFoundError):
            model_rec = AutoModel.load_from_folder(dir_path)

        os.remove(os.path.join(dir_path, "model.pt"))

        # check raises encoder.pkl is missing
        with pytest.raises(FileNotFoundError):
            model_rec = AutoModel.load_from_folder(dir_path)

        os.remove(os.path.join(dir_path, "model_config.json"))

        # check raises encoder.pkl is missing
        with pytest.raises(FileNotFoundError):
            model_rec = AutoModel.load_from_folder(dir_path)


class Test_Model_forward:
    @pytest.fixture
    def demo_data(self):
        data = torch.load(os.path.join(PATH, "data/mnist_clean_train_dataset_sample"))[
            :
        ]
        return data  # This is an extract of 3 data from MNIST (unnormalized) used to test custom architecture

    @pytest.fixture
    def wae(self, model_configs, demo_data):
        model_configs.input_dim = tuple(demo_data["data"][0].shape)
        return WAE_MMD(model_configs)

    def test_model_train_output(self, wae, demo_data):

        wae.train()

        out = wae(demo_data)

        assert isinstance(out, ModelOutput)

        assert set(["loss", "recon_loss", "mmd_loss", "recon_x", "z"]) == set(
            out.keys()
        )

        assert out.z.shape[0] == demo_data["data"].shape[0]
        assert out.recon_x.shape == demo_data["data"].shape


@pytest.mark.slow
class Test_WAE_MMD_Training:
    @pytest.fixture
    def train_dataset(self):
        return torch.load(os.path.join(PATH, "data/mnist_clean_train_dataset_sample"))

    @pytest.fixture(
        params=[BaseTrainerConfig(num_epochs=3, steps_saving=2, learning_rate=1e-5)]
    )
    def training_configs(self, tmpdir, request):
        tmpdir.mkdir("dummy_folder")
        dir_path = os.path.join(tmpdir, "dummy_folder")
        request.param.output_dir = dir_path
        return request.param

    @pytest.fixture(
        params=[
            torch.rand(1),
            torch.rand(1),
            torch.rand(1),
            torch.rand(1),
            torch.rand(1),
        ]
    )
    def wae(self, model_configs, custom_encoder, custom_decoder, request):
        # randomized

        alpha = request.param

        if alpha < 0.25:
            model = WAE_MMD(model_configs)

        elif 0.25 <= alpha < 0.5:
            model = WAE_MMD(model_configs, encoder=custom_encoder)

        elif 0.5 <= alpha < 0.75:
            model = WAE_MMD(model_configs, decoder=custom_decoder)

        else:
            model = WAE_MMD(
                model_configs, encoder=custom_encoder, decoder=custom_decoder
            )

        return model

    @pytest.fixture(params=[Adam])
    def optimizers(self, request, wae, training_configs):
        if request.param is not None:
            optimizer = request.param(
                wae.parameters(), lr=training_configs.learning_rate
            )

        else:
            optimizer = None

        return optimizer

    def test_wae_train_step(self, wae, train_dataset, training_configs, optimizers):
        trainer = BaseTrainer(
            model=wae,
            train_dataset=train_dataset,
            training_config=training_configs,
            optimizer=optimizers,
        )

        start_model_state_dict = deepcopy(trainer.model.state_dict())

        step_1_loss = trainer.train_step(epoch=1)

        step_1_model_state_dict = deepcopy(trainer.model.state_dict())

        # check that weights were updated
        assert not all(
            [
                torch.equal(start_model_state_dict[key], step_1_model_state_dict[key])
                for key in start_model_state_dict.keys()
            ]
        )

    def test_wae_eval_step(self, wae, train_dataset, training_configs, optimizers):
        trainer = BaseTrainer(
            model=wae,
            train_dataset=train_dataset,
            eval_dataset=train_dataset,
            training_config=training_configs,
            optimizer=optimizers,
        )

        start_model_state_dict = deepcopy(trainer.model.state_dict())

        step_1_loss = trainer.eval_step(epoch=1)

        step_1_model_state_dict = deepcopy(trainer.model.state_dict())

        # check that weights were not updated
        assert all(
            [
                torch.equal(start_model_state_dict[key], step_1_model_state_dict[key])
                for key in start_model_state_dict.keys()
            ]
        )

    def test_wae_predict_step(
        self, wae, train_dataset, training_configs, optimizers
    ):
        trainer = BaseTrainer(
            model=wae,
            train_dataset=train_dataset,
            eval_dataset=train_dataset,
            training_config=training_configs,
            optimizer=optimizers,
        )

        start_model_state_dict = deepcopy(trainer.model.state_dict())

        inputs, recon, generated = trainer.predict(trainer.model)

        step_1_model_state_dict = deepcopy(trainer.model.state_dict())

        # check that weights were not updated
        assert all(
            [
                torch.equal(start_model_state_dict[key], step_1_model_state_dict[key])
                for key in start_model_state_dict.keys()
            ]
        )

        assert torch.equal(inputs.cpu(), train_dataset.data.cpu())
        assert recon.shape == inputs.shape
        assert generated.shape == inputs.shape 

    def test_wae_main_train_loop(
        self, tmpdir, wae, train_dataset, training_configs, optimizers
    ):

        trainer = BaseTrainer(
            model=wae,
            train_dataset=train_dataset,
            eval_dataset=train_dataset,
            training_config=training_configs,
            optimizer=optimizers,
        )

        start_model_state_dict = deepcopy(trainer.model.state_dict())

        trainer.train()

        step_1_model_state_dict = deepcopy(trainer.model.state_dict())

        # check that weights were updated
        assert not all(
            [
                torch.equal(start_model_state_dict[key], step_1_model_state_dict[key])
                for key in start_model_state_dict.keys()
            ]
        )

    def test_checkpoint_saving(
        self, tmpdir, wae, train_dataset, training_configs, optimizers
    ):

        dir_path = training_configs.output_dir

        trainer = BaseTrainer(
            model=wae,
            train_dataset=train_dataset,
            training_config=training_configs,
            optimizer=optimizers,
        )

        # Make a training step
        step_1_loss = trainer.train_step(epoch=1)

        model = deepcopy(trainer.model)
        optimizer = deepcopy(trainer.optimizer)

        trainer.save_checkpoint(dir_path=dir_path, epoch=0, model=model)

        checkpoint_dir = os.path.join(dir_path, "checkpoint_epoch_0")

        assert os.path.isdir(checkpoint_dir)

        files_list = os.listdir(checkpoint_dir)

        assert set(["model.pt", "optimizer.pt", "training_config.json"]).issubset(
            set(files_list)
        )

        # check pickled custom decoder
        if not wae.model_config.uses_default_decoder:
            assert "decoder.pkl" in files_list

        else:
            assert not "decoder.pkl" in files_list

        # check pickled custom encoder
        if not wae.model_config.uses_default_encoder:
            assert "encoder.pkl" in files_list

        else:
            assert not "encoder.pkl" in files_list

        model_rec_state_dict = torch.load(os.path.join(checkpoint_dir, "model.pt"))[
            "model_state_dict"
        ]

        assert all(
            [
                torch.equal(
                    model_rec_state_dict[key].cpu(), model.state_dict()[key].cpu()
                )
                for key in model.state_dict().keys()
            ]
        )

        # check reload full model
        model_rec = AutoModel.load_from_folder(os.path.join(checkpoint_dir))

        assert all(
            [
                torch.equal(
                    model_rec.state_dict()[key].cpu(), model.state_dict()[key].cpu()
                )
                for key in model.state_dict().keys()
            ]
        )

        assert type(model_rec.encoder.cpu()) == type(model.encoder.cpu())
        assert type(model_rec.decoder.cpu()) == type(model.decoder.cpu())

        optim_rec_state_dict = torch.load(os.path.join(checkpoint_dir, "optimizer.pt"))

        assert all(
            [
                dict_rec == dict_optimizer
                for (dict_rec, dict_optimizer) in zip(
                    optim_rec_state_dict["param_groups"],
                    optimizer.state_dict()["param_groups"],
                )
            ]
        )

        assert all(
            [
                dict_rec == dict_optimizer
                for (dict_rec, dict_optimizer) in zip(
                    optim_rec_state_dict["state"], optimizer.state_dict()["state"]
                )
            ]
        )

    def test_checkpoint_saving_during_training(
        self, tmpdir, wae, train_dataset, training_configs, optimizers
    ):
        #
        target_saving_epoch = training_configs.steps_saving

        dir_path = training_configs.output_dir

        trainer = BaseTrainer(
            model=wae,
            train_dataset=train_dataset,
            training_config=training_configs,
            optimizer=optimizers,
        )

        model = deepcopy(trainer.model)

        trainer.train()

        training_dir = os.path.join(
            dir_path, f"WAE_MMD_training_{trainer._training_signature}"
        )
        assert os.path.isdir(training_dir)

        checkpoint_dir = os.path.join(
            training_dir, f"checkpoint_epoch_{target_saving_epoch}"
        )

        assert os.path.isdir(checkpoint_dir)

        files_list = os.listdir(checkpoint_dir)

        # check files
        assert set(["model.pt", "optimizer.pt", "training_config.json"]).issubset(
            set(files_list)
        )

        # check pickled custom decoder
        if not wae.model_config.uses_default_decoder:
            assert "decoder.pkl" in files_list

        else:
            assert not "decoder.pkl" in files_list

        # check pickled custom encoder
        if not wae.model_config.uses_default_encoder:
            assert "encoder.pkl" in files_list

        else:
            assert not "encoder.pkl" in files_list

        model_rec_state_dict = torch.load(os.path.join(checkpoint_dir, "model.pt"))[
            "model_state_dict"
        ]

        assert not all(
            [
                torch.equal(model_rec_state_dict[key], model.state_dict()[key])
                for key in model.state_dict().keys()
            ]
        )

    def test_final_model_saving(
        self, tmpdir, wae, train_dataset, training_configs, optimizers
    ):

        dir_path = training_configs.output_dir

        trainer = BaseTrainer(
            model=wae,
            train_dataset=train_dataset,
            training_config=training_configs,
            optimizer=optimizers,
        )

        trainer.train()

        model = deepcopy(trainer._best_model)

        training_dir = os.path.join(
            dir_path, f"WAE_MMD_training_{trainer._training_signature}"
        )
        assert os.path.isdir(training_dir)

        final_dir = os.path.join(training_dir, f"final_model")
        assert os.path.isdir(final_dir)

        files_list = os.listdir(final_dir)

        assert set(["model.pt", "model_config.json", "training_config.json"]).issubset(
            set(files_list)
        )

        # check pickled custom decoder
        if not wae.model_config.uses_default_decoder:
            assert "decoder.pkl" in files_list

        else:
            assert not "decoder.pkl" in files_list

        # check pickled custom encoder
        if not wae.model_config.uses_default_encoder:
            assert "encoder.pkl" in files_list

        else:
            assert not "encoder.pkl" in files_list

        # check reload full model
        model_rec = AutoModel.load_from_folder(os.path.join(final_dir))

        assert all(
            [
                torch.equal(
                    model_rec.state_dict()[key].cpu(), model.state_dict()[key].cpu()
                )
                for key in model.state_dict().keys()
            ]
        )

        assert type(model_rec.encoder.cpu()) == type(model.encoder.cpu())
        assert type(model_rec.decoder.cpu()) == type(model.decoder.cpu())

    def test_wae_training_pipeline(self, tmpdir, wae, train_dataset, training_configs):

        dir_path = training_configs.output_dir

        # build pipeline
        pipeline = TrainingPipeline(model=wae, training_config=training_configs)

        assert pipeline.training_config.__dict__ == training_configs.__dict__

        # Launch Pipeline
        pipeline(
            train_data=train_dataset.data,  # gives tensor to pipeline
            eval_data=train_dataset.data,  # gives tensor to pipeline
        )

        model = deepcopy(pipeline.trainer._best_model)

        training_dir = os.path.join(
            dir_path, f"WAE_MMD_training_{pipeline.trainer._training_signature}"
        )
        assert os.path.isdir(training_dir)

        final_dir = os.path.join(training_dir, f"final_model")
        assert os.path.isdir(final_dir)

        files_list = os.listdir(final_dir)

        assert set(["model.pt", "model_config.json", "training_config.json"]).issubset(
            set(files_list)
        )

        # check pickled custom decoder
        if not wae.model_config.uses_default_decoder:
            assert "decoder.pkl" in files_list

        else:
            assert not "decoder.pkl" in files_list

        # check pickled custom encoder
        if not wae.model_config.uses_default_encoder:
            assert "encoder.pkl" in files_list

        else:
            assert not "encoder.pkl" in files_list

        # check reload full model
        model_rec = AutoModel.load_from_folder(os.path.join(final_dir))

        assert all(
            [
                torch.equal(
                    model_rec.state_dict()[key].cpu(), model.state_dict()[key].cpu()
                )
                for key in model.state_dict().keys()
            ]
        )

        assert type(model_rec.encoder.cpu()) == type(model.encoder.cpu())
        assert type(model_rec.decoder.cpu()) == type(model.decoder.cpu())

class Test_WAE_Generation:
    @pytest.fixture
    def train_data(self):
        return torch.load(os.path.join(PATH, "data/mnist_clean_train_dataset_sample")).data

    @pytest.fixture()
    def ae_model(self):
        return WAE_MMD(WAE_MMD_Config(input_dim=(1, 28, 28), latent_dim=7))

    @pytest.fixture(
        params=[
            NormalSamplerConfig(),
            GaussianMixtureSamplerConfig(),
            MAFSamplerConfig(),
            IAFSamplerConfig()
        ]
    )
    def sampler_configs(self, request):
        return request.param

    def test_fits_in_generation_pipeline(self, ae_model, sampler_configs, train_data):
        pipeline = GenerationPipeline(model=ae_model, sampler_config=sampler_configs)
        gen_data = pipeline(
            num_samples=11,
            batch_size=7,
            output_dir=None,
            return_gen=True,
            train_data=train_data,
            eval_data=train_data,
            training_config=BaseTrainerConfig(num_epochs=1)
        )

        assert gen_data.shape[0] == 11